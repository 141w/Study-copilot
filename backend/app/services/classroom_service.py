"""
Classroom service — AI 互动课堂核心服务。

职责：
  1. 打包 Study Copilot 文档 → 提交 AI 互动课堂生成请求
  2. 提交课堂生成任务 + 轮询生成进度
  3. 接收课堂 Webhook 回调，自动创建/更新 CourseSpace 课程空间
  4. 同步课堂测验与答题记录到 Quiz 系统
  5. 容灾保障：当外部渲染服务不可达时，自动降级为本地课程大纲与测验生成
"""

import hashlib
import hmac
import json
import logging
import os
from typing import Any
from uuid import uuid4

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import CourseSpace, DocumentChunk, Quiz, QuizResult, User
from app.services import document_service
from app.services.course_service import add_document_to_course, create_course_space

logger = logging.getLogger(__name__)


def _check_enabled() -> None:
    """如果互动课堂未启用则报错。"""
    if not settings.classroom_enabled:
        raise RuntimeError("AI 互动课堂功能未启用（CLASSROOM_ENABLED=false）")


# ── 文档内容提取 ─────────────────────────────────────────────────────────────


async def _read_document_text(db: AsyncSession, doc_id: str) -> str:
    """从 DocumentChunk 提取原文拼成连续文本。"""
    result = await db.execute(
        select(DocumentChunk.content)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = [row[0] for row in result.all()]
    return "\n\n".join(chunks)


# ── Classroom Generation ─────────────────────────────────────────────────────


async def sync_classroom_providers(db: AsyncSession, user: User | None = None) -> bool:
    """将用户配置的 LLM、TTS 与生图模型同步至 OpenMAIC 的 server-providers.yml 与 .env.local。"""
    try:
        from app.services.config_service import get_llm_config_with_secret

        secret_cfg: dict[str, Any] = {}
        if not user:
            from sqlalchemy import select

            from app.db.database import UserLLMConfig

            res = await db.execute(
                select(User)
                .join(UserLLMConfig, User.id == UserLLMConfig.user_id)
                .order_by(UserLLMConfig.updated_at.desc())
            )
            user = res.scalars().first()
            if not user:
                res = await db.execute(select(User))
                user = res.scalars().first()

        if user:
            secret_cfg = await get_llm_config_with_secret(db, user)
        cls_cfg = secret_cfg.get("classroom_config") or {}

        # 1. 教学大模型配置
        if cls_cfg.get("use_custom_llm"):
            llm_key = (
                cls_cfg.get("classroom_llm_api_key")
                or secret_cfg.get("api_key")
                or settings.openai_api_key
                or "dummy-key"
            )
            llm_base_url = (
                cls_cfg.get("classroom_llm_base_url")
                or secret_cfg.get("base_url")
                or settings.openai_base_url
                or "https://api.openai.com/v1"
            ).rstrip("/")
            llm_model = (
                cls_cfg.get("classroom_llm_model")
                or secret_cfg.get("model_name")
                or settings.openai_model
                or "step-3.7-flash"
            )
        else:
            llm_key = secret_cfg.get("api_key") or settings.openai_api_key or "dummy-key"
            llm_base_url = (
                secret_cfg.get("base_url")
                or settings.openai_base_url
                or "https://api.openai.com/v1"
            ).rstrip("/")
            llm_model = (
                secret_cfg.get("model_name")
                or settings.openai_model
                or "step-3.7-flash"
            )

        # 2. TTS 语音合成配置
        # OpenMAIC 的 TTS 提供器统一指向 Study Copilot 兼容网关 (http://localhost:8000/api/tts/v1)
        # 该端点负责代理调用用户的自定义 TTS 模型并适配角色音色，且在第三方服务异常时无缝降级至高质量 Edge-TTS
        tts_enabled = cls_cfg.get("tts_enabled", True)
        tts_key = "study-copilot-local"
        tts_base_url = "http://localhost:8000/api/tts/v1"
        tts_models = ["edge-tts", "tts-1"]

        # 3. 图像生成配置
        image_enabled = cls_cfg.get("image_enabled", False)
        image_key = cls_cfg.get("image_api_key") or secret_cfg.get("api_key") or ""
        raw_img_base = (
            cls_cfg.get("image_base_url")
            or secret_cfg.get("base_url")
            or "https://api.openai.com/v1"
        ).strip().rstrip("/")
        if not raw_img_base.endswith("/v1") and not raw_img_base.endswith("/v1/images"):
            image_base_url = f"{raw_img_base}/v1"
        else:
            image_base_url = raw_img_base
        image_model = cls_cfg.get("image_model") or "gpt-image-2"

        # 组装 server-providers.yml 数据结构
        yaml_data: dict[str, Any] = {
            "providers": {
                "openai": {
                    "apiKey": llm_key,
                    "baseUrl": llm_base_url,
                    "models": [llm_model],
                }
            }
        }
        if tts_enabled:
            yaml_data["tts"] = {
                "openai-tts": {
                    "apiKey": tts_key,
                    "baseUrl": tts_base_url,
                    "models": tts_models,
                }
            }
        if image_enabled and image_key:
            yaml_data["image"] = {
                "openai-image": {
                    "apiKey": image_key,
                    "baseUrl": image_base_url,
                    "models": [image_model],
                }
            }

        # 4. 联网检索配置 (Web Search)
        ws_enabled = cls_cfg.get("web_search_enabled", False)
        ws_provider = (cls_cfg.get("web_search_provider") or "bocha").strip()
        ws_key = cls_cfg.get("web_search_api_key") or ""
        ws_base_url = (cls_cfg.get("web_search_base_url") or "").strip()
        if (ws_enabled or ws_key) and ws_provider:
            ws_entry: dict[str, Any] = {}
            if ws_key:
                ws_entry["apiKey"] = ws_key
            if ws_base_url:
                ws_entry["baseUrl"] = ws_base_url
            yaml_data["web-search"] = {
                ws_provider: ws_entry
            }

        # 5. 随堂语音识别 (ASR) 配置
        asr_enabled = cls_cfg.get("asr_enabled", True)
        asr_provider = (cls_cfg.get("asr_provider") or "browser-native").strip()
        asr_key = cls_cfg.get("asr_api_key") or ""
        asr_base_url = (cls_cfg.get("asr_base_url") or "").strip()
        asr_model = (cls_cfg.get("asr_model") or "whisper-1").strip()
        if asr_enabled and asr_provider != "browser-native" and asr_key:
            asr_entry: dict[str, Any] = {
                "apiKey": asr_key,
                "models": [asr_model],
            }
            if asr_base_url:
                asr_entry["baseUrl"] = asr_base_url
            yaml_data["asr"] = {
                asr_provider: asr_entry
            }

        classroom_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../classroom")
        )
        if os.path.exists(classroom_dir):
            yaml_path = os.path.join(classroom_dir, "server-providers.yml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)
            logger.info("Synced classroom providers to %s", yaml_path)

            env_local_path = os.path.join(classroom_dir, ".env.local")
            lines = []
            if os.path.exists(env_local_path):
                with open(env_local_path, encoding="utf-8") as f:
                    for line in f:
                        if not line.startswith("DEFAULT_MODEL=") and line.strip():
                            lines.append(line.rstrip("\n"))
            if not any("ALLOWED_FRAME_ANCESTORS" in l for l in lines):
                lines.append(
                    'ALLOWED_FRAME_ANCESTORS="http://localhost:3000 http://127.0.0.1:3000"'
                )
            lines.append(f'DEFAULT_MODEL="openai:{llm_model}"')
            with open(env_local_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

        return True
    except Exception as e:
        logger.warning("Failed to sync classroom providers: %s", e)
        return False


async def build_classroom_request(
    db: AsyncSession,
    user: User,
    doc_ids: list[str],
    requirement: str,
    enable_web_search: bool = False,
    enable_tts: bool = True,
    enable_image_generation: bool = False,
    agent_mode: str = "default",
) -> dict[str, Any]:
    """组装课堂生成请求体。最多带 5 篇文档文本内容。"""
    _check_enabled()

    cls_cfg: dict[str, Any] = {}
    # 自动对齐用户在模型配置中保存的生图、TTS、联网检索与阵容模式
    try:
        from app.services.config_service import get_llm_config_with_secret

        secret_cfg = await get_llm_config_with_secret(db, user)
        cls_cfg = secret_cfg.get("classroom_config") or {}
        if not enable_image_generation and cls_cfg.get("image_enabled"):
            enable_image_generation = True
        if cls_cfg.get("tts_enabled") is not None:
            enable_tts = bool(cls_cfg.get("tts_enabled"))
        if not enable_web_search and cls_cfg.get("web_search_enabled"):
            enable_web_search = True
        if agent_mode == "default" and cls_cfg.get("agent_mode"):
            agent_mode = str(cls_cfg.get("agent_mode") or agent_mode)
    except Exception as e:
        logger.debug("Failed to read user classroom config: %s", e)

    docs = []
    for doc_id in doc_ids[:5]:
        doc = await document_service.get_document(db, user, doc_id)
        text = await _read_document_text(db, doc_id)
        docs.append(
            {
                "text": text[:50_000],  # 单文档上限 50k 字符
                "filename": doc["filename"],
            }
        )

    combined_text = "\n\n---\n\n".join(
        [f"【参考文档：{d['filename']}】\n{d['text']}" for d in docs if d.get("text")]
    )
    pdf_content = (
        {"text": combined_text, "images": []}
        if combined_text
        else None
    )

    req_payload: dict[str, Any] = {
        "requirement": requirement or "请根据提供的材料生成课程",
        "pdfContent": pdf_content,
        "enableWebSearch": enable_web_search,
        "enableTTS": enable_tts,
        "enableImageGeneration": enable_image_generation,
        "agentMode": agent_mode,
        "doc_ids": doc_ids,
    }
    if enable_web_search:
        req_payload["webSearchProviderId"] = cls_cfg.get("web_search_provider") or "bocha"
        ws_key = cls_cfg.get("web_search_api_key")
        if ws_key:
            req_payload["webSearchApiKey"] = ws_key

    return req_payload


async def submit_classroom_generation(
    payload: dict[str, Any],
    db: AsyncSession | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """调用 OpenMAIC 外部课堂引擎 POST /api/generate-classroom，返回 job 信息。

    本项目采用 OpenMAIC 外部引擎作为唯一专业课堂引擎。
    若引擎不可达，直接返回明确错误指导用户启动服务，杜绝简陋假课件。
    """
    _check_enabled()

    if db and user:
        await sync_classroom_providers(db, user)

    base_url = (settings.classroom_base_url or "").rstrip("/")
    if not base_url:
        raise RuntimeError("未配置 AI 互动课堂引擎服务地址（CLASSROOM_BASE_URL）。")

    url = f"{base_url}/api/generate-classroom"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        logger.info("Classroom generation submitted to OpenMAIC: jobId=%s", data.get("jobId", "?"))
        return data
    except httpx.ConnectError as ce:
        logger.error("Failed to connect to OpenMAIC at %s: %s", url, ce)
        raise RuntimeError(
            "AI 互动课堂引擎（OpenMAIC，端口 3001）未启动或连接被拒绝。请确认服务已启动（运行 ./start.sh 或进入 classroom 目录运行 pnpm dev）。"
        ) from ce
    except httpx.TimeoutException as te:
        logger.error("Timeout connecting to OpenMAIC at %s: %s", url, te)
        raise RuntimeError(
            "连接 AI 互动课堂引擎（OpenMAIC 3001）超时，请检查课堂服务状态。"
        ) from te
    except httpx.HTTPStatusError as hse:
        err_msg = ""
        try:
            err_json = hse.response.json()
            err_msg = err_json.get("error") or err_json.get("details") or str(err_json)
        except Exception:
            err_msg = hse.response.text[:200]
        logger.error("OpenMAIC classroom generation rejected (%s): %s", hse.response.status_code, err_msg)
        raise RuntimeError(f"AI 互动课堂引擎生成失败 ({hse.response.status_code}): {err_msg}") from hse
    except Exception as e:
        logger.error("OpenMAIC classroom generation request failed (%s): %s", url, e, exc_info=True)
        raise RuntimeError(f"AI 互动课堂引擎生成请求失败: {e}") from e


async def poll_generation_status(job_id: str) -> dict[str, Any]:
    """轮询课堂生成进度。"""
    _check_enabled()

    base_url = (settings.classroom_base_url or "").rstrip("/")
    if not base_url:
        raise RuntimeError("未配置 AI 互动课堂引擎服务地址（CLASSROOM_BASE_URL）。")

    url = f"{base_url}/api/generate-classroom/{job_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Failed to poll classroom status from %s: %s", url, e)
        raise

    raw = data.get("data", data) if isinstance(data, dict) else {}
    status_str = raw.get("status", "unknown")
    is_done = raw.get("done") is True or status_str in ("succeeded", "completed", "failed")
    return {
        "job_id": job_id,
        "status": status_str,
        "step": raw.get("step", ""),
        "progress": raw.get("progress", 100 if is_done else 0),
        "message": raw.get("message", ""),
        "scenes_generated": raw.get("scenesGenerated", 0) or raw.get("scenes_generated", 0),
        "total_scenes": raw.get("totalScenes", 0) or raw.get("total_scenes", 0),
        "done": is_done,
        "result": raw.get("result"),
        "error": raw.get("error"),
    }


async def sync_completed_classroom_job(
    db: AsyncSession,
    user: User,
    job_id: str,
    job_info: dict[str, Any],
) -> dict[str, Any] | None:
    """当轮询发现课堂任务完成时，就地更新占位课程并同步测验（双通道自愈）。"""
    raw_data = job_info.get("data") if isinstance(job_info, dict) else None
    payload: dict[str, Any] = (
        raw_data if isinstance(raw_data, dict) else (job_info if isinstance(job_info, dict) else {})
    )
    status = payload.get("status", "")
    is_done = payload.get("done") is True or status in ("succeeded", "completed")
    if not is_done:
        return None

    result = payload.get("result") or {}
    classroom_id = (
        result.get("id")
        or result.get("classroomId")
        or payload.get("classroomId")
        or payload.get("id")
        or job_id
    )
    url = result.get("url") or payload.get("url") or f"/classroom-engine/classroom/{classroom_id}"
    title = (
        (result.get("stage") or {}).get("name") or result.get("title") or payload.get("title") or ""
    )

    quiz_results = payload.get("quiz_results") or result.get("quiz_results") or []
    if not quiz_results and "scenes" in result:
        for s in result.get("scenes", []):
            if isinstance(s, dict) and s.get("type") == "quiz":
                content = s.get("content") or {}
                for q in content.get("questions", []):
                    ans = q.get("answer", "")
                    if isinstance(ans, list):
                        ans = ",".join(ans)
                    quiz_results.append(
                        {
                            "question": q.get("question", ""),
                            "options": q.get("options", []),
                            "correct_answer": str(ans),
                            "explanation": q.get("explanation", ""),
                            "user_answer": "",
                            "is_correct": False,
                        }
                    )

    escaped = job_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    matched = await db.execute(
        select(CourseSpace)
        .where(
            CourseSpace.user_id == user.id,
            CourseSpace.description.like(f"%{escaped}%"),
        )
        .order_by(CourseSpace.created_at.desc())
        .limit(1)
    )
    course_row = matched.scalar_one_or_none()

    if not course_row and classroom_id:
        escaped_cid = classroom_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        matched_cid = await db.execute(
            select(CourseSpace)
            .where(
                CourseSpace.user_id == user.id,
                CourseSpace.description.like(f"%{escaped_cid}%"),
            )
            .order_by(CourseSpace.created_at.desc())
            .limit(1)
        )
        course_row = matched_cid.scalar_one_or_none()

    callback_payload = {
        "event": "classroom_completed",
        "classroom_id": classroom_id,
        "title": title
        or (course_row.name.replace("（生成中）", "") if course_row else "AI 互动课堂"),
        "url": url,
        "quiz_results": quiz_results,
    }
    return await handle_webhook_callback(db, user, callback_payload, matched_course=course_row)


# ── Webhook 处理 ─────────────────────────────────────────────────────────────


def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """验证课堂 webhook HMAC 签名。"""
    if not settings.classroom_webhook_secret:
        if settings.debug:
            logger.warning("CLASSROOM_WEBHOOK_SECRET 未配置且 DEBUG=True：开发模式放行（生产必配）")
            return True
        logger.error("CLASSROOM webhook 被拒绝：未配置 CLASSROOM_WEBHOOK_SECRET（fail-closed）")
        return False
    if not signature:
        return False
    expected = hmac.new(
        settings.classroom_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_webhook_callback(
    db: AsyncSession,
    user: User,
    payload: dict[str, Any],
    matched_course: CourseSpace | None = None,
) -> dict[str, Any]:
    """处理课堂引擎回调，创建/更新 CourseSpace。"""
    event = payload.get("event", "")
    logger.info("Classroom webhook: event=%s", event)

    if event == "classroom_completed":
        existing_doc_ids = []
        if matched_course is not None:
            course_row = matched_course
            title = payload.get("title") or course_row.name
            course_row.name = title
            if course_row.description:
                try:
                    desc_obj = json.loads(course_row.description)
                    if isinstance(desc_obj, dict):
                        existing_doc_ids = desc_obj.get("source_doc_ids", [])
                except Exception:
                    pass
        else:
            course_row = await create_course_space(
                db,
                user,
                name=payload.get("title", "未命名课堂"),
                description=payload.get("description", ""),
                color="#409EFF",
            )

        doc_ids = payload.get("doc_ids") or payload.get("source_doc_ids") or existing_doc_ids
        for d_id in doc_ids:
            try:
                await add_document_to_course(db, user, course_row.id, d_id)
            except Exception as link_err:
                logger.warning(
                    "Failed to link doc %s to course %s in webhook: %s",
                    d_id,
                    course_row.id,
                    link_err,
                )

        cid = payload.get("classroom_id", "")
        internal_url = f"/courses/{course_row.id}/classroom"
        course_row.description = json.dumps(
            {
                "classroom_url": payload.get("url") or internal_url,
                "internal_classroom_url": internal_url,
                "engine_url": f"/classroom-engine/classroom/{cid}",
                "classroom_id": cid,
                "description": payload.get("description", ""),
                "event": event,
                "source_doc_ids": doc_ids,
            },
            ensure_ascii=False,
        )
        await db.commit()

        # 同步 quiz 结果
        quiz_results = payload.get("quiz_results", [])
        synced = await sync_quiz_results(db, user, quiz_results)

        logger.info(
            "Classroom synced: course_id=%s, quizzes=%d",
            course_row.id,
            synced,
        )
        return {"course_id": course_row.id, "quizzes_synced": synced}

    return {"status": "ignored", "event": event}


# ── Quiz 同步 ────────────────────────────────────────────────────────────────


async def sync_quiz_results(
    db: AsyncSession,
    user: User,
    quiz_results: list[dict[str, Any]],
) -> int:
    """将课堂测验结果写入 Study Copilot 的 QuizResult 表。"""
    if not quiz_results:
        return 0

    count = 0
    for qr in quiz_results:
        try:
            quiz = Quiz(
                id=str(uuid4()),
                document_id=None,
                question_type="multiple_choice",
                question=qr.get("question", ""),
                options=json.dumps(qr.get("options", []), ensure_ascii=False),
                answer=qr.get("correct_answer", ""),
                explanation=qr.get("explanation", ""),
            )
            db.add(quiz)
            await db.flush()

            result = QuizResult(
                id=str(uuid4()),
                quiz_id=quiz.id,
                user_id=user.id,
                user_answer=qr.get("user_answer", ""),
                is_correct=qr.get("is_correct", False),
            )
            db.add(result)
            count += 1
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning("Failed to sync quiz result: %s", qr, exc_info=True)

    await db.commit()
    return count
