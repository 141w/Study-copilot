"""
Course Generator — 基于文档内容自动生成课程大纲 + 测验。

使用已有的 LLM + QuizGenerator + Transformations 能力，
不引入新依赖。

流程：
  1. 拼装文档上下文（从 DocumentChunk 读取）
  2. LLM 生成课程大纲（JSON：标题 + 章节列表）
  3. 每章节生成测验题（复用 QuizGenerator）
  4. 返回结构化课程数据（前端或 service 层负责创建 CourseSpace）
"""

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm import LLM
from app.core.quiz_generator import quiz_generator
from app.db import Document, DocumentChunk, User

logger = logging.getLogger(__name__)

# ── 文档上下文提取 ────────────────────────────────────────────────────────────


def _build_context_from_chunks(chunks: list[dict], max_chars: int = 8000) -> str:
    """从文档块拼装 LLM 可消费的上下文文本。"""
    parts: list[str] = []
    total = 0
    for c in chunks:
        text = c.get("content", "").strip()
        if not text:
            continue
        sep_len = 2 if parts else 0
        if total + sep_len + len(text) > max_chars:
            remaining = max_chars - total - sep_len
            if remaining <= 0:
                break
            parts.append(text[:remaining])
            break
        parts.append(text)
        total += sep_len + len(text)
    return "\n\n".join(parts)


async def _load_document_context(
    db: AsyncSession, doc_ids: list[str], user_id: str, max_chars: int = 8000
) -> str:
    """从多个文档加载文本上下文，校验文档归属当前用户。"""
    if not doc_ids:
        return ""
    result = await db.execute(
        select(DocumentChunk.content, DocumentChunk.document_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.document_id.in_(doc_ids),
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    rows = result.all()
    return _build_context_from_chunks(
        [{"content": r[0], "document_id": r[1]} for r in rows],
        max_chars=max_chars,
    )


# ── 课程大纲生成 ─────────────────────────────────────────────────────────────


OUTLINE_PROMPT_PREFIX = """你是一位顶尖的课程教学设计师与视觉创意总监。请根据提供的文档内容，生成一份结构严谨、视觉生动的课程大纲。

要求：
1. 课程标题要专业、精炼、有启发性
2. 包含 3-5 个逻辑递进的章节，每章有明确的学习目标
3. 每章包含 2-4 个关键知识点
4. 难度标注：入门 / 进阶 / 深入
5. 为全课封面设计一段细致生动的英文生图提示词 (cover_image_prompt)：
   - 必须使用纯英文；
   - 描述具体的 3D 概念场景、代表性学习隐喻实体、空间景深、科技学术光影氛围；
   - 必须注明无文字、无字母符号 (strictly no text, no typography)；
6. 为前两个核心章节分别设计一段英文概念图解生图提示词 (image_prompt)：
   - 必须使用纯英文；
   - 描述该章节核心知识点的 3D 实体图解、剖面结构或知识连接模型；
   - 同样必须注明无文字、无字母符号 (strictly no text, no typography)；

返回 JSON 格式（严禁包含任何其他文字或 Markdown 代码块标记）：
{
  "title": "课程标题",
  "description": "课程核心内容与学习价值概述（2-3句话）",
  "difficulty": "入门",
  "cover_image_prompt": "A modern 3D isometric conceptual diorama visualizing the core theme of ..., floating glowing nodes, soft studio lighting, glass and matte textures, strictly no text",
  "sections": [
    {
      "id": "s1",
      "title": "章节标题",
      "objective": "本章学习目标",
      "difficulty": "入门",
      "key_points": ["知识点1", "知识点2"],
      "image_prompt": "A detailed 3D infographic diorama explaining ..., translucent acrylic modules, isometric view, warm ambient lighting, strictly no text"
    }
  ]
}"""


def build_refined_image_prompt(
    title: str,
    context_details: str = "",
    is_cover: bool = True,
    custom_prompt: str = "",
) -> str:
    """构建用于高品质 AI 生图（FLUX.1 / DALL-E 3 / 通义万相等）的精细视觉提示词。

    设计原则：
    1. 具象化实体与空间构图（Isometric 3D 透视 / 微缩模型 / 空间深度）
    2. 材质与光影（磨砂亚克力微光、柔和全局光照、细致景深、哑光陶瓷质感）
    3. 现代科技学术色彩基调（深蓝与蓝青主色、琥珀亮色点缀、高雅通透）
    4. 严格负向约束（严禁伪英文字符、假文字、水印、杂乱几何）
    """
    scene = (custom_prompt or "").strip()
    if not scene:
        if is_cover:
            scene = (
                f"A modern 3D isometric conceptual diorama visualizing '{title}', featuring symbolic learning artifacts, "
                f"floating translucent glass nodes, illuminated connection pathways, and interactive futuristic knowledge elements"
            )
            if context_details:
                scene += f", contextualized around {context_details[:120]}"
        else:
            scene = (
                f"A detailed 3D infographic illustration representing '{title}', visualizing concepts like {context_details or 'core structural principles'}, "
                f"showing intricate interconnected modular components, cutaway view, and clear visual hierarchy"
            )

    quality_modifiers = [
        "isometric 3D render",
        "soft ambient occlusion studio lighting",
        "subtle warm rim light",
        "translucent frosted acrylic and matte ceramic textures",
        "clean gradient studio background with elegant depth of field",
        "harmonious color palette with deep navy blue, crisp cyan, and soft amber accents",
        "Octane Render and C4D aesthetics",
        "hyper-detailed, balanced minimalist composition, 8k resolution",
        "strictly no text, no typography, no letters, no words, no watermarks",
    ]

    return f"{scene}, {', '.join(quality_modifiers)}"


async def generate_outline(
    context: str,
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调用 LLM 生成课程大纲。"""
    llm = LLM.from_config(llm_config)
    prompt = f"{OUTLINE_PROMPT_PREFIX}\n\n文档内容：\n{context[:6000]}"

    try:
        raw = await llm.generate(
            prompt,
            system_prompt="你是课程设计专家。只返回 JSON，不要其他文字。",
            temperature=0.5,
            max_tokens=2048,
        )
        if raw:
            # 清理 Markdown 代码块标记
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()
            match = re.search(r"\{[\s\S]+\}", cleaned)
            if match:
                json_str = match.group()
                json_str = re.sub(r",\s*([\]}])", r"\1", json_str)
                return json.loads(json_str)
    except Exception as e:
        logger.warning("Failed to parse generated outline JSON: %s", e)

    # Fallback
    return {
        "title": "未命名课程",
        "description": "基于文档自动生成的课程",
        "difficulty": "入门",
        "sections": [
            {
                "id": f"s{i}",
                "title": f"第 {i + 1} 部分",
                "objective": "学习核心概念",
                "difficulty": "入门",
                "key_points": ["要点"],
            }
            for i in range(3)
        ],
    }


# ── 综合生成 ─────────────────────────────────────────────────────────────────


async def generate_course(
    db: AsyncSession,
    user: User,
    doc_ids: list[str],
    requirement: str = "",
    llm_config: dict[str, Any] | None = None,
    enable_image_generation: bool = False,
) -> dict[str, Any]:
    """完整的课程生成流程。

    参数
    ----
    doc_ids : list[str]
        源文档 ID（需属于该 user）。
    requirement : str
        用户对课程主题/风格的要求（可选）。
    llm_config : dict | None
        LLM 配置，None 则使用用户的默认配置。
    enable_image_generation : bool
        是否为课程生成 AI 配图封面。

    返回
    ----
    { outline, quizzes }  — 结构化课程数据，前端负责展示和创建 CourseSpace。
    """
    # 1. 加载文档上下文（仅限当前用户的非删除文档）
    context = await _load_document_context(db, doc_ids, user.id, max_chars=8000)
    if not context:
        context = f"用户要求：{requirement}" if requirement else "（无文档内容）"

    # 2. 用户要求注入
    if requirement:
        context = f"用户课程要求：{requirement}\n\n文档内容：\n{context}"

    # 2.5 获取用户自定 LLM 配置
    if llm_config is None and user is not None:
        try:
            from app.services.config_service import get_llm_config_with_secret

            llm_config = await get_llm_config_with_secret(db, user)
        except Exception as e:
            logger.warning("Failed to fetch user LLM config: %s", e)

    # 3. 生成大纲
    outline = await generate_outline(context, llm_config)

    # 4. 为每个章节并发生成测验（使用用户自定模型配置）
    import asyncio

    from app.core.quiz_generator import QuizGenerator

    q_gen = QuizGenerator(llm_config) if llm_config else quiz_generator

    async def _gen_section_quizzes(section: dict[str, Any]) -> list[dict[str, Any]]:
        title = section.get("title", "")
        sec_id = section.get("id", str(uuid.uuid4()))
        key_points = section.get("key_points", [])
        section_context = f"{title}: {', '.join(key_points)}\n\n{context[:3000]}"
        try:
            sec_qs = await q_gen.generate_quizzes(
                section_context, choice_count=2, short_answer_count=1
            )
        except Exception as qe:
            logger.warning("Quiz generation failed for section %s: %s", title, qe)
            sec_qs = []
        for q in sec_qs:
            q["section_id"] = sec_id
            q["section_title"] = title
        return sec_qs

    section_tasks = [_gen_section_quizzes(sec) for sec in outline.get("sections", [])[:5]]
    section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
    quizzes: list[dict[str, Any]] = []
    for res in section_results:
        if isinstance(res, list):
            quizzes.extend(res)

    # 5. 若配置了专属生图模型或开启了生图，异步为课程生成配图封面与核心概念插画
    cls_cfg = (llm_config or {}).get("classroom_config") or {}
    should_gen_image = enable_image_generation or cls_cfg.get("image_enabled", False)
    effective_img_key = (
        cls_cfg.get("image_api_key") or (llm_config or {}).get("api_key") or settings.openai_api_key
    )

    if should_gen_image and effective_img_key:
        img_cfg = {**cls_cfg, "image_api_key": effective_img_key}
        try:
            from app.core.image_generator import generate_image

            course_title = outline.get("title") or "AI Course"
            course_desc = outline.get("description") or ""
            cover_llm_prompt = outline.get("cover_image_prompt") or ""
            img_prompt = build_refined_image_prompt(
                title=course_title,
                context_details=course_desc,
                is_cover=True,
                custom_prompt=cover_llm_prompt,
            )
            img_res = await generate_image(
                prompt=img_prompt,
                config=img_cfg,
                size=cls_cfg.get("image_size") or "1024x1024",
            )
            if img_res.get("url"):
                outline["cover_image"] = img_res["url"]
            elif img_res.get("b64_json"):
                outline["cover_image"] = f"data:image/png;base64,{img_res['b64_json']}"
            logger.info("Course cover image generated successfully for: %s", course_title)
        except Exception as ie:
            logger.warning("Optional course cover image generation skipped/failed: %s", ie)

        # 为前 1~2 个核心概念章节异步生成概念示意图/信息图插画
        for sec in outline.get("sections", [])[:2]:
            sec_title = sec.get("title") or ""
            kps_str = ", ".join(sec.get("key_points", [])[:3])
            sec_llm_prompt = sec.get("image_prompt") or ""
            c_prompt = build_refined_image_prompt(
                title=sec_title,
                context_details=kps_str,
                is_cover=False,
                custom_prompt=sec_llm_prompt,
            )
            try:
                c_res = await generate_image(
                    prompt=c_prompt,
                    config=img_cfg,
                    size="1024x1024",
                )
                if c_res.get("url"):
                    sec["illustration_image"] = c_res["url"]
                elif c_res.get("b64_json"):
                    sec["illustration_image"] = f"data:image/png;base64,{c_res['b64_json']}"
                logger.info("Concept section illustration generated for: %s", sec_title)
            except Exception as ce:
                logger.warning(
                    "Concept illustration generation skipped for '%s': %s", sec_title, ce
                )

    logger.info(
        "Course generated: %d sections, %d quizzes",
        len(outline.get("sections", [])),
        len(quizzes),
    )

    stage_id = str(uuid.uuid4())
    classroom_data = build_classroom_dsl(
        stage_id=stage_id,
        outline=outline,
        quizzes=quizzes,
        cover_image=outline.get("cover_image"),
        tts_config=cls_cfg,
    )

    return {
        "outline": outline,
        "quizzes": quizzes,
        "source_doc_ids": doc_ids,
        "classroom_data": classroom_data,
    }


def save_classroom_dsl_to_disk(classroom_data: dict[str, Any]) -> str:
    """将生成的课件 DSL 写入 classroom/data/classrooms/{id}.json（同构兼容 Next.js 独立引擎）。"""
    classroom_id = classroom_data.get("id") or str(uuid.uuid4())
    root = Path(__file__).resolve().parent.parent.parent.parent
    target_dir = root / "classroom" / "data" / "classrooms"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{classroom_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(classroom_data, f, ensure_ascii=False, indent=2)
    return str(file_path)


def build_classroom_dsl(
    stage_id: str,
    outline: dict[str, Any],
    quizzes: list[dict[str, Any]],
    cover_image: str | None = None,
    tts_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成符合 @openmaic/dsl 规范的完整交互式微课课件 (PersistedClassroomData)。

    包含：
    - Stage: 舞台基础元数据、苏老师/学霸/求知同学多角色配置、TTS 绑定
    - Scene[]:
      - 导论幕 (Slide): 课程总览、学习目标、章节演播目录
      - 各章节正文幕 (Slide): 16:9 响应式 Canvas，含标题、知识点概念卡片、高亮边框与插画
      - 场景剧本 Actions: 教师导引 (Speech)、学生提问 (Speech)、学霸辨析 (Speech)、重点聚光 (Spotlight)
      - 随堂检测幕 (Quiz): 交互式题目、选项、即时解析
      - 结语复盘幕 (Slide): 学习成就、知识要点沉淀与课后建议
    """
    now_ms = int(time.time() * 1000)
    course_title = outline.get("title") or "AI 互动微课"
    course_desc = outline.get("description") or "基于文档自动提炼的沉浸式多角色互动微课"
    sections = outline.get("sections") or []

    tts_cfg = tts_config or {}
    tts_prov = tts_cfg.get("tts_provider") or "edge-tts"
    is_openai_tts = tts_prov in ("openai", "siliconflow", "custom")
    v_teacher = tts_cfg.get("voice_teacher") or ("alloy" if is_openai_tts else "zh-CN-YunxiNeural")
    v_curious = tts_cfg.get("voice_curious") or (
        "nova" if is_openai_tts else "zh-CN-XiaoxiaoNeural"
    )
    v_thinker = tts_cfg.get("voice_thinker") or ("echo" if is_openai_tts else "zh-CN-YunjianNeural")

    stage = {
        "id": stage_id,
        "name": course_title,
        "description": course_desc,
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "style": "academic",
        "languageDirective": "zh-CN",
        "generatedAgentConfigs": [
            {
                "id": "teacher",
                "name": "苏老师",
                "role": "主讲导师",
                "persona": "温和耐心的学术导师，擅长提纲挈领与深入浅出，引导思考",
                "avatar": "GraduationCap",
                "color": "#3B82F6",
                "priority": 1,
                "voiceConfig": {"providerId": tts_prov, "voiceId": v_teacher},
            },
            {
                "id": "curious",
                "name": "求知同学",
                "role": "探索学员",
                "persona": "好奇心强，善于提出初学者最容易遇到的困惑、边界问题和应用难点",
                "avatar": "User",
                "color": "#F59E0B",
                "priority": 2,
                "voiceConfig": {"providerId": tts_prov, "voiceId": v_curious},
            },
            {
                "id": "thinker",
                "name": "学霸",
                "role": "深度思考者",
                "persona": "逻辑严密，善于结构化提炼、对比分析与寻找底层规律",
                "avatar": "Brain",
                "color": "#10B981",
                "priority": 3,
                "voiceConfig": {"providerId": tts_prov, "voiceId": v_thinker},
            },
        ],
    }

    scenes: list[dict[str, Any]] = []
    scene_order = 0

    # 1. 导论幕 (Intro Scene)
    intro_canvas_id = f"slide-intro-{uuid.uuid4().hex[:6]}"
    intro_elements: list[dict[str, Any]] = [
        {
            "id": f"el-badge-{uuid.uuid4().hex[:6]}",
            "type": "shape",
            "left": 60,
            "top": 45,
            "width": 110,
            "height": 30,
            "fill": "#EFF6FF",
            "outline": {"color": "#3B82F6", "width": 1, "style": "solid"},
            "text": "AI 互动微课",
        },
        {
            "id": f"el-title-{uuid.uuid4().hex[:6]}",
            "type": "text",
            "left": 60,
            "top": 85,
            "width": 880,
            "height": 55,
            "content": course_title,
            "fontSize": 28,
            "defaultColor": "#1E293B",
            "lineHeight": 1.2,
        },
        {
            "id": f"el-desc-card-{uuid.uuid4().hex[:6]}",
            "type": "shape",
            "left": 60,
            "top": 150,
            "width": 880,
            "height": 85,
            "fill": "#F8FAFC",
            "outline": {"color": "#E2E8F0", "width": 1, "style": "solid"},
            "text": f"【课程目标】\n{course_desc}",
        },
    ]

    if cover_image:
        intro_elements.append(
            {
                "id": f"el-cover-{uuid.uuid4().hex[:6]}",
                "type": "image",
                "left": 60,
                "top": 250,
                "width": 260,
                "height": 260,
                "src": cover_image,
            }
        )
        catalog_left = 340
        catalog_width = 600
    else:
        catalog_left = 60
        catalog_width = 880

    sec_summary_text = "\n".join(
        [
            f"• 第 {i + 1} 幕：{s.get('title')} ({s.get('difficulty', '基础')})"
            for i, s in enumerate(sections[:5])
        ]
    )
    intro_elements.append(
        {
            "id": f"el-catalog-{uuid.uuid4().hex[:6]}",
            "type": "shape",
            "left": catalog_left,
            "top": 250,
            "width": catalog_width,
            "height": 260,
            "fill": "#FFFFFF",
            "outline": {"color": "#E2E8F0", "width": 1, "style": "solid"},
            "text": f"【本课章节演播目录】\n{sec_summary_text}",
        }
    )

    intro_scene = {
        "id": f"scene-intro-{uuid.uuid4().hex[:8]}",
        "stageId": stage_id,
        "title": f"导论：{course_title}",
        "order": scene_order,
        "type": "slide",
        "content": {
            "type": "slide",
            "canvas": {
                "id": intro_canvas_id,
                "viewportSize": 1000,
                "viewportRatio": 0.5625,
                "theme": {
                    "backgroundColor": "#F8FAFC",
                    "themeColors": ["#3B82F6", "#10B981", "#F59E0B", "#6366F1"],
                    "fontColor": "#1E293B",
                    "fontName": "PingFang SC, Microsoft YaHei, sans-serif",
                },
                "elements": intro_elements,
            },
        },
        "actions": [
            {
                "id": f"act-intro-1-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "teacher",
                "text": f"同学们好！欢迎来到本节 AI 互动微课《{course_title}》。本课将通过多角色研讨与随堂检测，帮助大家系统掌握核心知识。",
                "voice": v_teacher,
            },
            {
                "id": f"act-intro-2-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "curious",
                "text": "苏老师，这门课主要涉及哪些核心要点？我们应该如何抓住关键脉络？",
                "voice": v_curious,
            },
            {
                "id": f"act-intro-3-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "thinker",
                "text": "从大纲编排来看，课程由浅入深，涵盖了关键原理与实际应用。建议大家在每幕随堂测验时重点验证理解。",
                "voice": v_thinker,
            },
            {
                "id": f"act-intro-4-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "teacher",
                "text": "学霸总结得很清晰。下面我们正式进入第一幕的学习！",
                "voice": v_teacher,
            },
        ],
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }
    scenes.append(intro_scene)
    scene_order += 1

    # 2. 各章节正文与随堂测验幕
    for sec_idx, sec in enumerate(sections[:6]):
        sec_id = sec.get("id") or str(uuid.uuid4())
        sec_title = sec.get("title") or f"第 {sec_idx + 1} 节"
        objective = sec.get("objective") or "掌握核心知识点"
        difficulty = sec.get("difficulty") or "进阶"
        kps = sec.get("key_points") or ["核心原理"]

        # 构建章节幻灯片
        sec_canvas_id = f"slide-{sec_idx + 1}-{uuid.uuid4().hex[:6]}"
        card_1_id = f"el-card-1-{uuid.uuid4().hex[:6]}"
        card_2_id = f"el-card-2-{uuid.uuid4().hex[:6]}"

        sec_elements: list[dict[str, Any]] = [
            {
                "id": f"el-badge-s-{sec_idx}",
                "type": "shape",
                "left": 60,
                "top": 40,
                "width": 140,
                "height": 28,
                "fill": "#EFF6FF",
                "outline": {"color": "#3B82F6", "width": 1, "style": "solid"},
                "text": f"第 {sec_idx + 1} 幕 · {difficulty}",
            },
            {
                "id": f"el-title-s-{sec_idx}",
                "type": "text",
                "left": 60,
                "top": 76,
                "width": 880,
                "height": 48,
                "content": sec_title,
                "fontSize": 24,
                "defaultColor": "#1E293B",
                "lineHeight": 1.2,
            },
            {
                "id": f"el-obj-s-{sec_idx}",
                "type": "shape",
                "left": 60,
                "top": 132,
                "width": 880,
                "height": 60,
                "fill": "#F1F5F9",
                "outline": {"color": "#CBD5E1", "width": 1, "style": "solid"},
                "text": f"🎯 【学习目标】: {objective}",
            },
        ]

        kp1_text = kps[0] if len(kps) > 0 else "关键原理与核心概念"
        kp2_text = kps[1] if len(kps) > 1 else "应用实践与常见难点"

        sec_img = sec.get("illustration_image")
        if sec_img:
            sec_elements.append(
                {
                    "id": f"el-img-s-{sec_idx}",
                    "type": "image",
                    "left": 60,
                    "top": 210,
                    "width": 380,
                    "height": 300,
                    "src": sec_img,
                }
            )
            sec_elements.append(
                {
                    "id": card_1_id,
                    "type": "shape",
                    "left": 460,
                    "top": 210,
                    "width": 480,
                    "height": 300,
                    "fill": "#FFFFFF",
                    "outline": {"color": "#3B82F6", "width": 2, "style": "solid"},
                    "text": f"💡 【核心概念解析】\n\n• {kp1_text}\n• {kp2_text}\n\n🎯 实践落地指引：\n- 结合图解直观理解核心逻辑\n- 关注关键机制与边界约束",
                }
            )
        else:
            sec_elements.append(
                {
                    "id": card_1_id,
                    "type": "shape",
                    "left": 60,
                    "top": 210,
                    "width": 420,
                    "height": 300,
                    "fill": "#FFFFFF",
                    "outline": {"color": "#3B82F6", "width": 2, "style": "solid"},
                    "text": f"💡 【重点一】\n\n{kp1_text}\n\n• 核心要义与关键逻辑\n• 系统架构中的作用与地位",
                }
            )
            sec_elements.append(
                {
                    "id": card_2_id,
                    "type": "shape",
                    "left": 520,
                    "top": 210,
                    "width": 420,
                    "height": 300,
                    "fill": "#FFFFFF",
                    "outline": {"color": "#10B981", "width": 2, "style": "solid"},
                    "text": f"🔍 【重点二】\n\n{kp2_text}\n\n• 实践落地规范与注意要点\n• 常见误区与深度辨析",
                }
            )

        sec_actions = [
            {
                "id": f"act-s{sec_idx}-1",
                "type": "speech",
                "agentId": "teacher",
                "text": f"现在我们进入第 {sec_idx + 1} 幕：《{sec_title}》。本幕的目标是：{objective}。",
                "voice": v_teacher,
            },
            {
                "id": f"act-s{sec_idx}-2",
                "type": "spotlight",
                "elementId": card_1_id,
                "dimOpacity": 0.35,
            },
            {
                "id": f"act-s{sec_idx}-3",
                "type": "speech",
                "agentId": "teacher",
                "text": f"首先看核心重点：“{kp1_text}”。大家注意把握它的基础机制与来龙去脉。",
                "voice": v_teacher,
            },
            {
                "id": f"act-s{sec_idx}-4",
                "type": "speech",
                "agentId": "curious",
                "text": f"苏老师，关于“{kp1_text}”，如果遇到复杂场景，最关键的切入点是什么？",
                "voice": v_curious,
            },
            {
                "id": f"act-s{sec_idx}-5",
                "type": "spotlight",
                "elementId": card_2_id if not sec_img else card_1_id,
                "dimOpacity": 0.35,
            },
            {
                "id": f"act-s{sec_idx}-6",
                "type": "speech",
                "agentId": "thinker",
                "text": f"可以结合要点中的“{kp2_text}”来看。两者互为补充，理解了规范与应用边界，就不容易踩坑。",
                "voice": v_thinker,
            },
            {
                "id": f"act-s{sec_idx}-7",
                "type": "speech",
                "agentId": "teacher",
                "text": "学霸讲得切中要害。让我们巩固这两点，准备进入本幕的挑战练习。",
                "voice": v_teacher,
            },
        ]

        sec_scene = {
            "id": f"scene-{sec_idx + 1}-{uuid.uuid4().hex[:8]}",
            "stageId": stage_id,
            "title": f"第 {sec_idx + 1} 幕：{sec_title}",
            "order": scene_order,
            "type": "slide",
            "content": {
                "type": "slide",
                "canvas": {
                    "id": sec_canvas_id,
                    "viewportSize": 1000,
                    "viewportRatio": 0.5625,
                    "theme": {
                        "backgroundColor": "#F8FAFC",
                        "themeColors": ["#3B82F6", "#10B981", "#F59E0B", "#6366F1"],
                        "fontColor": "#1E293B",
                        "fontName": "PingFang SC, Microsoft YaHei, sans-serif",
                    },
                    "elements": sec_elements,
                },
            },
            "actions": sec_actions,
            "createdAt": now_ms,
            "updatedAt": now_ms,
        }
        scenes.append(sec_scene)
        scene_order += 1

        # 随堂测验幕
        sec_quizzes = [
            q
            for q in quizzes
            if q.get("section_id") == sec_id or q.get("section_title") == sec_title
        ]
        if not sec_quizzes and quizzes:
            sec_quizzes = [quizzes[sec_idx % len(quizzes)]]

        if sec_quizzes:
            quiz_questions: list[dict[str, Any]] = []
            for q_idx, q in enumerate(sec_quizzes[:2]):
                opts = []
                for o_idx, opt in enumerate(q.get("options") or []):
                    if isinstance(opt, dict):
                        lbl = opt.get("content") or opt.get("label") or opt.get("text") or str(opt)
                        val = opt.get("key") or opt.get("value") or chr(65 + o_idx)
                    else:
                        lbl = str(opt)
                        val = chr(65 + o_idx)
                    opts.append({"label": lbl, "value": val})
                if not opts:
                    opts = [{"label": "正确", "value": "A"}, {"label": "错误", "value": "B"}]

                ans = q.get("correct_answer") or ["A"]
                if isinstance(ans, str):
                    ans = [ans]

                quiz_questions.append(
                    {
                        "id": str(q.get("id") or f"q-{sec_idx}-{q_idx}"),
                        "type": "single" if q.get("question_type") != "multiple" else "multiple",
                        "question": q.get("question") or f"关于《{sec_title}》的核心考查",
                        "options": opts,
                        "answer": ans,
                        "analysis": q.get("explanation")
                        or q.get("analysis")
                        or "掌握本章核心逻辑即可得出正确答案。",
                        "points": 10,
                    }
                )

            quiz_scene = {
                "id": f"scene-quiz-{sec_idx + 1}-{uuid.uuid4().hex[:8]}",
                "stageId": stage_id,
                "title": f"随堂挑战 · {sec_title}",
                "order": scene_order,
                "type": "quiz",
                "content": {
                    "type": "quiz",
                    "questions": quiz_questions,
                },
                "actions": [
                    {
                        "id": f"act-qz-{sec_idx}-1",
                        "type": "speech",
                        "agentId": "teacher",
                        "text": f"学习完《{sec_title}》，苏老师为大家准备了随堂挑战，请在屏幕上直接作答！",
                        "voice": "zh-CN-YunxiNeural",
                    },
                    {
                        "id": f"act-qz-{sec_idx}-2",
                        "type": "speech",
                        "agentId": "curious",
                        "text": "这道题很有针对性，我也来做一下，看看理解到位了没有！",
                        "voice": "zh-CN-XiaoxiaoNeural",
                    },
                ],
                "createdAt": now_ms,
                "updatedAt": now_ms,
            }
            scenes.append(quiz_scene)
            scene_order += 1

    # 3. 结语幕 (Outro Scene)
    outro_scene = {
        "id": f"scene-outro-{uuid.uuid4().hex[:8]}",
        "stageId": stage_id,
        "title": "课程总结与结语",
        "order": scene_order,
        "type": "slide",
        "content": {
            "type": "slide",
            "canvas": {
                "id": f"slide-outro-{uuid.uuid4().hex[:6]}",
                "viewportSize": 1000,
                "viewportRatio": 0.5625,
                "theme": {
                    "backgroundColor": "#F8FAFC",
                    "themeColors": ["#3B82F6", "#10B981", "#F59E0B", "#6366F1"],
                    "fontColor": "#1E293B",
                    "fontName": "PingFang SC, Microsoft YaHei, sans-serif",
                },
                "elements": [
                    {
                        "id": f"el-badge-end-{uuid.uuid4().hex[:6]}",
                        "type": "shape",
                        "left": 60,
                        "top": 50,
                        "width": 140,
                        "height": 30,
                        "fill": "#ECFDF5",
                        "outline": {"color": "#10B981", "width": 1, "style": "solid"},
                        "text": "🎉 结课复盘",
                    },
                    {
                        "id": f"el-title-end-{uuid.uuid4().hex[:6]}",
                        "type": "text",
                        "left": 60,
                        "top": 95,
                        "width": 880,
                        "height": 55,
                        "content": f"恭喜完成《{course_title}》学习！",
                        "fontSize": 28,
                        "defaultColor": "#1E293B",
                        "lineHeight": 1.2,
                    },
                    {
                        "id": f"el-card-end-{uuid.uuid4().hex[:6]}",
                        "type": "shape",
                        "left": 60,
                        "top": 170,
                        "width": 880,
                        "height": 320,
                        "fill": "#FFFFFF",
                        "outline": {"color": "#E2E8F0", "width": 1, "style": "solid"},
                        "text": "🏆 【学习成果沉淀】\n\n1. 已完整通晓本课程核心章节与关键知识点体系；\n2. 顺利完成随堂交互式测验，建立了体系化认知；\n3. 建议点击「返回课程」进入错题本或问答研讨模式进一步加深掌握！",
                    },
                ],
            },
        },
        "actions": [
            {
                "id": f"act-end-1-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "teacher",
                "text": f"祝贺各位同学顺利学完《{course_title}》的所有内容！大家展现了非常好的求知状态。",
                "voice": v_teacher,
            },
            {
                "id": f"act-end-2-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "thinker",
                "text": "学完后建议结合课件大纲和错题解析再复盘一遍，加深记忆痕迹。",
                "voice": v_thinker,
            },
            {
                "id": f"act-end-3-{uuid.uuid4().hex[:6]}",
                "type": "speech",
                "agentId": "curious",
                "text": "收获满满！谢谢苏老师和学霸学长的细心指导！",
                "voice": v_curious,
            },
        ],
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }
    scenes.append(outro_scene)

    return {
        "id": stage_id,
        "url": f"/courses/{stage_id}/classroom",
        "stage": stage,
        "scenes": scenes,
        "scenesCount": len(scenes),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
