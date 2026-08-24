import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.rate_limit import IPRateLimiter
from app.db import User, get_db
from app.exceptions import RateLimitError
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["问答"])

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
