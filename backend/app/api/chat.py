from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json

from app.db import get_db, ChatSession, Message
from app.api.auth import get_current_user, User
from app.core.rag_engine import rag_engine
from app.core.config import get_user_llm_config
from app.core.rate_limit import IPRateLimiter

router = APIRouter(prefix="/chat", tags=["问答"])

# 创建限流器
_chat_limiter = IPRateLimiter(requests_per_minute=30)


class AskRequest(BaseModel):
    question: str
    document_ids: List[str]
    session_id: Optional[str] = None
    config: Optional[dict] = None
    stream: Optional[bool] = False  # 新增：是否使用流式输出


class Source(BaseModel):
    index: int
    document_id: str
    text: str
    page: Optional[str] = ""
    source: Optional[str] = ""
    relevance_score: float


class SourceWithIndex(BaseModel):
    index: int
    document_id: str
    text: str
    page: Optional[str] = ""
    source: Optional[str] = ""
    relevance_score: float


class AskResponse(BaseModel):
    answer: str
    sources: List[Source]
    used_source_indices: List[int] = []
    filtered_sources: List[Source] = []
    session_id: str


class MessageResp(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[List[Source]] = None
    created_at: str


class ChatHistoryResp(BaseModel):
    session_id: str
    title: str
    messages: List[MessageResp]
    created_at: str


@router.post("/ask")
async def ask(
    request: Request,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 手动限流检查
    if not _chat_limiter.check(request):
        raise HTTPException(
            status_code=429, 
            detail="请求过于频繁，请稍后再试"
        )
    if not req.document_ids:
        raise HTTPException(status_code=400, detail="请选择文档")

    # 获取用户配置（优先使用请求中的config，否则使用数据库配置）
    user_config = await get_user_llm_config(db, current_user.id)
    llm_config = req.config if req.config else user_config

    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        new_session = ChatSession(
            id=session_id, user_id=current_user.id, title=req.question[:50]
        )
        db.add(new_session)
        await db.commit()

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    msgs = msg_result.scalars().all()
    history = []
    for m in msgs:
        history.append({"role": m.role, "content": m.content})

    # 流式模式
    if req.stream:
        async def generate_stream():
            answer_parts = []
            async for chunk in rag_engine.ask_stream(req.document_ids, req.question, history, llm_config):
                if chunk["type"] == "sources":
                    yield f"data: {json.dumps({'type': 'sources', 'sources': chunk['sources'], 'filtered_sources': chunk['filtered_sources'], 'session_id': session_id}, ensure_ascii=False)}\n\n"
                elif chunk["type"] == "token":
                    answer_parts.append(chunk["content"])
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                elif chunk["type"] == "answer":
                    yield f"data: {json.dumps({'type': 'answer', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
            
            # 流式结束后，保存消息到数据库
            full_answer = "".join(answer_parts)
            sources_json = json.dumps([], ensure_ascii=False)  # 来源已在stream中发送
            user_msg = Message(
                id=str(uuid.uuid4()), session_id=session_id, role="user", content=req.question
            )
            ai_msg = Message(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=full_answer,
                sources=sources_json,
            )
            db.add(user_msg)
            db.add(ai_msg)
            await db.commit()
            
            # 发送结束标记
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    # 非流式模式（原有逻辑）
    result = await rag_engine.ask(req.document_ids, req.question, history, llm_config)

    sources_json = json.dumps(result.get("sources", []), ensure_ascii=False)
    user_msg = Message(
        id=str(uuid.uuid4()), session_id=session_id, role="user", content=req.question
    )
    ai_msg = Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        sources=sources_json,
    )
    db.add(user_msg)
    db.add(ai_msg)
    await db.commit()

    return AskResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result.get("sources", [])],
        used_source_indices=result.get("used_source_indices", []),
        filtered_sources=[Source(**s) for s in result.get("filtered_sources", [])],
        session_id=session_id,
    )


@router.get("/history", response_model=List[ChatHistoryResp])
async def get_sessions(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()

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
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    msg_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    msgs = msg_result.scalars().all()

    def parse_sources(sources_str):
        if not sources_str:
            return None
        try:
            return [Source(**s) for s in json.loads(sources_str)]
        except:
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
                created_at=str(m.created_at)
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
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    await db.delete(session)
    await db.commit()

    return {"message": "删除成功"}


class UpdateTitleRequest(BaseModel):
    title: str


@router.put("/history/{session_id}")
async def update_session_title(
    session_id: str,
    req: UpdateTitleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    session.title = req.title
    await db.commit()

    return {"message": "更新成功", "title": req.title}
