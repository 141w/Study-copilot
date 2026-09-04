import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.rate_limit import IPRateLimiter
from app.db import Document, User, get_db
from app.exceptions import RateLimitError
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


class PersonaConfig(BaseModel):
    name: str
    system_message: str


class DiscussRequest(BaseModel):
    question: str
    document_ids: list[str] | None = None
    personas: list[PersonaConfig] | None = None
    max_turns: int = 2
    # 批次10：上下文来源模式。rag_snippets（默认）= RAG 检索前 5 条片段；
    # full_docs = document_bundle 全文打包（CJK 1M 预算，多文档带来源头），
    # 适合短文档/材料整体讨论而非事实问答
    context_mode: Literal["rag_snippets", "full_docs"] = "rag_snippets"


class MessageResp(BaseModel):
    id: str
    role: str
    content: str
    sources: list[Source] | None = None
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

    def parse_sources(sources_str):
        if not sources_str:
            return None
        try:
            return [Source(**s) for s in json.loads(sources_str)]
        except Exception:
            return None

    return ChatHistoryResp(
        session_id=session.id,
        title=session.title or "新对话",
        messages=[
            MessageResp(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=parse_sources(m.sources),
                created_at=str(m.created_at),
            )
            for m in msgs
        ],
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
    from app.services.config_service import get_llm_config_with_secret
    user_config = await get_llm_config_with_secret(db, current_user)

    # 可选上下文（批次10：接入 document_bundle，两种模式）
    # 安全修复：doc_ids 先过归属校验——原实现（含 rag_snippets 路径）直接把
    # 任意 doc_id 喂给检索层，越权可读其他用户的文档内容
    context = ""
    doc_ids = req.document_ids or []
    if doc_ids:
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
                question=req.question,
                history=[],
                llm_config=user_config,
            )
            context = "\n".join(
                s.get("text", "") for s in rag_result.get("sources", [])[:5]
            )
        except Exception as exc:
            logger.warning("RAG context fetch failed for discussion: %s", exc)

    personas = [{"name": p.name, "system_message": p.system_message} for p in (req.personas or [])]

    async def generate_stream():
        try:
            from app.core.persona_discussion import discuss
            async for event in discuss(
                topic=req.question,
                personas=personas,
                context=context,
                llm_config=user_config,
                max_turns=req.max_turns,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'讨论服务暂时不可用：{e}'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
