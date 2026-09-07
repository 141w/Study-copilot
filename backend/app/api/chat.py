import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_optional_user
from app.core.rate_limit import IPRateLimiter
from app.db import CustomPersona, Document, Message, User, get_db
from app.exceptions import NotFoundError, RateLimitError, ValidationError
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["问答"])
logger = logging.getLogger(__name__)

_chat_limiter = IPRateLimiter(requests_per_minute=30)


# ── Schemas ────────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    question: str
    document_ids: list[str]
    session_id: str | None = None
    config: dict | None = None
    stream: bool | None = False


class Source(BaseModel):
    index: int
    document_id: str
    text: str
    page: str | None = ""
    source: str | None = ""
    relevance_score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    used_source_indices: list[int] = []
    filtered_sources: list[Source] = []
    session_id: str


class CreatePersonaReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    system_message: str = Field(..., min_length=1, max_length=4000)
    role: str | None = Field(None, max_length=50)
    avatar: str = Field("User", max_length=50)
    color: str | None = Field("#6366f1", max_length=20)


class UpdatePersonaReq(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    system_message: str | None = Field(None, min_length=1, max_length=4000)
    role: str | None = Field(None, max_length=50)
    avatar: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=20)


class PersonaConfig(BaseModel):
    name: str | None = None
    system_message: str | None = None
    role: str | None = None
    avatar: str | None = None
    color: str | None = None
    id: str | None = None
    is_custom: bool | None = False


class DiscussRequest(BaseModel):
    question: str
    document_ids: list[str] | None = None
    personas: list[PersonaConfig] | None = None
    max_turns: int = 2
    # 批次10：上下文来源模式。rag_snippets（默认）= RAG 检索前 5 条片段；
    # full_docs = document_bundle 全文打包（CJK 1M 预算，多文档带来源头），
    # 适合短文档/材料整体讨论而非事实问答
    context_mode: Literal["rag_snippets", "full_docs"] = "rag_snippets"
    session_id: str | None = None


class MessageResp(BaseModel):
    id: str
    role: str
    content: str
    sources: list[Source] | None = None
    discussion_turns: list[dict] | None = None
    discussionTurns: list[dict] | None = None  # noqa: N815
    personas: list[dict] | None = None
    summary: str | None = None
    created_at: str


class ChatHistoryResp(BaseModel):
    session_id: str
    title: str
    messages: list[MessageResp]
    created_at: str


class UpdateTitleRequest(BaseModel):
    title: str


class SearchRequest(BaseModel):
    query: str
    session_id: str | None = None
    top_k: int = 10


class SearchResult(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    similarity: float
    created_at: str


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/ask")
async def ask(
    request: Request,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _chat_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    if req.stream:

        async def generate_stream():
            try:
                async for event in chat_service.ask_question_stream(
                    db,
                    current_user,
                    req.question,
                    req.document_ids,
                    req.session_id,
                    req.config,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                # 上游异常（如模型不可达）转为可见事件并正常收尾，
                # 避免客户端在已发出的 200 流上无限等待
                yield f"data: {json.dumps({'type': 'error', 'message': f'服务暂时无法连接模型：{e}'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    result = await chat_service.ask_question(
        db,
        current_user,
        req.question,
        req.document_ids,
        req.session_id,
        req.config,
    )
    return AskResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result.get("sources", [])],
        used_source_indices=result.get("used_source_indices", []),
        filtered_sources=[Source(**s) for s in result.get("filtered_sources", [])],
        session_id=result["session_id"],
    )


@router.get("/history", response_model=list[ChatHistoryResp])
async def get_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = await chat_service.list_sessions(db, current_user)
    return [
        ChatHistoryResp(
            session_id=s.id,
            title=s.title or "新对话",
            messages=[],
            created_at=str(s.created_at),
        )
        for s in sessions
    ]


@router.get("/history/{session_id}", response_model=ChatHistoryResp)
async def get_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, msgs = await chat_service.get_session_history(db, current_user, session_id)

    def parse_message_payload(m: Message):
        sources = None
        discussion_turns = None
        personas = None
        summary = None
        if not m.sources:
            return sources, discussion_turns, personas, summary
        try:
            raw = json.loads(m.sources)
            if isinstance(raw, list):
                sources = [Source(**s) for s in raw]
            elif isinstance(raw, dict):
                if "sources" in raw and isinstance(raw["sources"], list):
                    sources = [Source(**s) for s in raw["sources"]]
                turns = raw.get("discussion_turns") or raw.get("discussionTurns")
                if isinstance(turns, list):
                    discussion_turns = turns
                summary = raw.get("summary")
                personas = raw.get("personas")
        except Exception:
            pass
        return sources, discussion_turns, personas, summary

    messages_resp = []
    for m in msgs:
        sources, discussion_turns, personas, summary = parse_message_payload(m)
        messages_resp.append(
            MessageResp(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=sources,
                discussion_turns=discussion_turns,
                discussionTurns=discussion_turns,
                personas=personas,
                summary=summary,
                created_at=str(m.created_at),
            )
        )

    return ChatHistoryResp(
        session_id=session.id,
        title=session.title or "新对话",
        messages=messages_resp,
        created_at=str(session.created_at),
    )


@router.delete("/history/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await chat_service.delete_session(db, current_user, session_id)
    return {"message": "删除成功"}


@router.put("/history/{session_id}")
async def update_session_title(
    session_id: str,
    req: UpdateTitleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_title = await chat_service.update_session_title(db, current_user, session_id, req.title)
    return {"message": "更新成功", "title": new_title}


@router.post("/search", response_model=list[SearchResult])
async def search_messages(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not req.query or not req.query.strip():
        return []
    results = await chat_service.search_messages(db, current_user, req.query, req.session_id, req.top_k)
    return [SearchResult(**r) for r in results]


@router.get("/personas")
async def list_personas(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """获取多智能体讨论模式角色列表（内置预置角色 + 当前用户的自定义角色）。"""
    from app.core.persona_discussion import get_persona_presets

    presets = get_persona_presets()
    result_presets = [{**p, "is_custom": False} for p in presets]

    custom_personas = []
    if current_user:
        result = await db.execute(
            select(CustomPersona)
            .where(CustomPersona.user_id == current_user.id)
            .order_by(CustomPersona.created_at.asc())
        )
        for cp in result.scalars().all():
            custom_personas.append(
                {
                    "id": cp.id,
                    "name": cp.name,
                    "role": cp.role,
                    "avatar": cp.avatar,
                    "color": cp.color or "#6366f1",
                    "system_message": cp.system_message,
                    "is_custom": True,
                    "created_at": cp.created_at.isoformat() if cp.created_at else None,
                }
            )

    return {
        "personas": result_presets + custom_personas,
        "presets": result_presets,
        "custom": custom_personas,
    }


@router.post("/personas")
async def create_persona(
    req: CreatePersonaReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建当前用户的自定义研讨角色，存入数据库。"""
    name = req.name.strip()
    if not name:
        raise ValidationError("角色名称不能为空")
    system_message = req.system_message.strip()
    if not system_message:
        raise ValidationError("人设提示词不能为空")

    persona_id = str(uuid.uuid4())
    role = req.role.strip() if req.role else f"custom_{persona_id[:8]}"

    persona = CustomPersona(
        id=persona_id,
        user_id=current_user.id,
        name=name,
        role=role,
        avatar=req.avatar.strip() or "User",
        color=req.color.strip() if req.color else "#6366f1",
        system_message=system_message,
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    return {
        "id": persona.id,
        "name": persona.name,
        "role": persona.role,
        "avatar": persona.avatar,
        "color": persona.color,
        "system_message": persona.system_message,
        "is_custom": True,
        "created_at": persona.created_at.isoformat() if persona.created_at else None,
    }


@router.put("/personas/{persona_id}")
async def update_persona(
    persona_id: str,
    req: UpdatePersonaReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改当前用户的自定义研讨角色。"""
    result = await db.execute(
        select(CustomPersona).where(
            CustomPersona.id == persona_id,
            CustomPersona.user_id == current_user.id,
        )
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("自定义角色不存在或无权操作")

    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise ValidationError("角色名称不能为空")
        persona.name = name

    if req.system_message is not None:
        sm = req.system_message.strip()
        if not sm:
            raise ValidationError("人设提示词不能为空")
        persona.system_message = sm

    if req.avatar is not None:
        persona.avatar = req.avatar.strip() or "User"

    if req.color is not None:
        persona.color = req.color.strip() or "#6366f1"

    if req.role is not None:
        r = req.role.strip()
        if r:
            persona.role = r

    await db.commit()
    await db.refresh(persona)

    return {
        "id": persona.id,
        "name": persona.name,
        "role": persona.role,
        "avatar": persona.avatar,
        "color": persona.color,
        "system_message": persona.system_message,
        "is_custom": True,
        "created_at": persona.created_at.isoformat() if persona.created_at else None,
    }


@router.delete("/personas/{persona_id}")
async def delete_persona(
    persona_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除当前用户的自定义研讨角色。"""
    result = await db.execute(
        select(CustomPersona).where(
            CustomPersona.id == persona_id,
            CustomPersona.user_id == current_user.id,
        )
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("自定义角色不存在或无权操作")

    await db.delete(persona)
    await db.commit()
    return {"message": "角色已删除", "id": persona_id}


@router.post("/discuss")
async def discuss(
    request: Request,
    req: DiscussRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Multi-persona discussion mode.

    Streams events: persona_speak / summary / error / done.
    Optionally enriches the topic with RAG context from document_ids.
    """
    if not _chat_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    # 加载 LLM 配置
    user_config = None
    if current_user:
        from app.services.config_service import get_llm_config_with_secret
        user_config = await get_llm_config_with_secret(db, current_user)

    # 可选上下文（批次10：接入 document_bundle，两种模式）
    # 安全修复：doc_ids 先过归属校验——原实现（含 rag_snippets 路径）直接把
    # 任意 doc_id 喂给检索层，越权可读其他用户的文档内容
    context = ""
    doc_ids = req.document_ids or []
    if doc_ids:
        if current_user:
            owned_result = await db.execute(
                select(Document.id).where(
                    Document.id.in_(doc_ids),
                    Document.user_id == current_user.id,
                    Document.deleted_at.is_(None),
                )
            )
            owned_ids = {row[0] for row in owned_result.all()}
            dropped = [d for d in doc_ids if d not in owned_ids]
            if dropped:
                logger.warning("discuss: dropped %d non-owned doc_ids", len(dropped))
            doc_ids = list(owned_ids)
        else:
            doc_ids = []
    if doc_ids and req.context_mode == "full_docs":
        # 全文打包：多文档合并 + CJK 预算 + 来源标注（此前为孤儿模块，按
        # docs/5-INTEGRATION §3.3 设计意图接入）
        try:
            from app.core.document_bundle import build_bundle_from_doc_ids
            bundle = await build_bundle_from_doc_ids(db, doc_ids)
            if bundle.text:
                context = bundle.text
                if bundle.truncated:
                    logger.info("discussion bundle truncated at %d chars", bundle.total_chars)
        except Exception as exc:
            logger.warning("Bundle context build failed for discussion: %s", exc)
    elif doc_ids:
        try:
            from app.core.rag_engine import rag_engine
            rag_result = await rag_engine.ask(
                doc_ids=doc_ids,
                query=req.question,
                history=[],
                user_config=user_config,
            )
            context = "\n".join(
                s.get("text", "") for s in rag_result.get("sources", [])[:5]
            )
        except Exception as exc:
            logger.warning("RAG context fetch failed for discussion: %s", exc)

    # 查找并补全角色配置（若缺少 system_message 则从数据库或预置库补全）
    from app.core.persona_discussion import PERSONA_PRESETS

    needed_db_roles = set()
    for p in (req.personas or []):
        if not p.system_message:
            role_key = (p.role or p.name or "").lower()
            if role_key not in PERSONA_PRESETS:
                if p.id:
                    needed_db_roles.add(p.id)
                if p.role:
                    needed_db_roles.add(p.role)
                if p.name:
                    needed_db_roles.add(p.name)

    db_persona_map: dict[str, CustomPersona] = {}
    if needed_db_roles and current_user:
        cp_result = await db.execute(
            select(CustomPersona).where(
                CustomPersona.user_id == current_user.id,
                or_(
                    CustomPersona.id.in_(needed_db_roles),
                    CustomPersona.role.in_(needed_db_roles),
                    CustomPersona.name.in_(needed_db_roles),
                ),
            )
        )
        for cp in cp_result.scalars().all():
            db_persona_map[cp.id] = cp
            db_persona_map[cp.role] = cp
            db_persona_map[cp.name] = cp

    personas = []
    for p in (req.personas or []):
        p_name = p.name or ""
        p_sys = p.system_message or ""
        p_role = p.role or ""
        p_avatar = p.avatar or ""
        p_color = p.color or ""

        # 尝试从预置库补全
        if p_role:
            preset = PERSONA_PRESETS.get(p_role.lower())
            if preset:
                p_name = p_name or preset["name"]
                p_avatar = p_avatar or preset.get("avatar", "User")
                p_color = p_color or preset.get("color", "#6366f1")
                if not p_sys:
                    p_sys = preset.get("system_message", "")

        if not p_sys:
            match = (
                db_persona_map.get(p.id or "")
                or db_persona_map.get(p.role or "")
                or db_persona_map.get(p.name or "")
            )
            if match:
                p_name = p_name or match.name
                p_sys = match.system_message
                p_role = p_role or match.role
                p_avatar = p_avatar or match.avatar
                p_color = p_color or match.color or "#6366f1"

        personas.append(
            {
                "name": p_name or p_role or "研讨员",
                "system_message": p_sys,
                "role": p_role,
                "avatar": p_avatar or "User",
                "color": p_color or "#6366f1",
            }
        )

    # 确保会话存在并落库用户提问
    session_id, _ = await chat_service._ensure_session(
        db, current_user.id, req.session_id, req.question
    )
    q_emb = await chat_service._embed_text(req.question)
    user_msg_id = str(uuid.uuid4())
    await chat_service._insert_message(
        db, user_msg_id, session_id, "user", req.question, None, q_emb
    )

    async def generate_stream():
        # 首包下发会话 ID，支持前端会话绑定与历史同步
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"

        collected_turns: list[dict] = []
        summary_text = ""
        error_msg = ""
        active_persona_chunks: dict[str, str] = {}
        saved_to_db = False

        async def _save_discussion_record():
            nonlocal saved_to_db
            if saved_to_db:
                return
            saved_to_db = True
            content_parts = []
            for t in collected_turns:
                content_parts.append(f"【{t['persona']}】：{t['content']}")
            if summary_text:
                content_parts.append(f"\n\n---\n\n**讨论总结**\n\n{summary_text}")
            elif error_msg:
                content_parts.append(f"\n\n---\n\n{error_msg}")

            full_content = "\n\n".join(content_parts).strip()
            if not full_content:
                full_content = error_msg or "研讨结束"

            meta = {
                "type": "discussion",
                "discussion_turns": collected_turns,
                "summary": summary_text,
                "personas": [
                    {"name": p["name"], "avatar": p["avatar"], "color": p.get("color")}
                    for p in personas
                ],
            }
            if error_msg:
                meta["error"] = error_msg

            meta_json = json.dumps(meta, ensure_ascii=False)
            try:
                disc_emb = await chat_service._embed_text(full_content)
                disc_msg_id = str(uuid.uuid4())
                await chat_service._insert_message(
                    db, disc_msg_id, session_id, "discussion", full_content, meta_json, disc_emb
                )
            except Exception as save_err:
                logger.warning("Failed to save discussion message to DB: %s", save_err)

        try:
            from app.core.persona_discussion import discuss
            async for event in discuss(
                topic=req.question,
                personas=personas,
                context=context,
                llm_config=user_config,
                max_turns=req.max_turns,
            ):
                ev_type = event.get("type")
                if ev_type == "persona_start":
                    p_name = event.get("persona", "")
                    active_persona_chunks[p_name] = ""
                elif ev_type == "persona_chunk":
                    p_name = event.get("persona", "")
                    active_persona_chunks[p_name] = active_persona_chunks.get(p_name, "") + (event.get("delta") or "")
                elif ev_type == "persona_speak":
                    p_name = event.get("persona", "")
                    content = event.get("content") or active_persona_chunks.get(p_name, "")
                    turn_num = event.get("turn", 1)
                    collected_turns.append({
                        "id": f"turn-{len(collected_turns) + 1}",
                        "persona": p_name,
                        "avatar": event.get("avatar", "User"),
                        "color": event.get("color", "#6366f1"),
                        "content": content,
                        "turn": turn_num,
                    })
                elif ev_type == "summary_chunk":
                    summary_text += (event.get("delta") or "")
                elif ev_type == "summary":
                    summary_text = event.get("content") or summary_text
                elif ev_type == "error":
                    error_msg = str(event.get("message") or "")
                elif ev_type == "done":
                    await _save_discussion_record()

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_msg = f"讨论服务暂时不可用：{e}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        finally:
            await _save_discussion_record()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
