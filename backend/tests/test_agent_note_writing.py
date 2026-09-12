"""Tests for Agent note-taking capabilities:
1. Note metadata extraction (extract_note_metadata)
2. Query routing for NOTE_TAKING intent
3. Automatic note generation and persistence during chat
4. Manual saving of messages via POST /api/chat/messages/{message_id}/save-note
5. User isolation and history reconstruction with saved_note metadata
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.note_synthesizer import extract_note_metadata
from app.core.query_router import QueryRouter, QueryType
from app.db import ChatSession, Message, Note, User
from app.services import chat_service
from app.services.auth_service import create_access_token, get_password_hash


def _create_user(suffix: str = "") -> User:
    uid = uuid.uuid4().hex[:8]
    return User(
        id=f"note-user-{uid}{suffix}",
        username=f"noteuser_{uid}{suffix}",
        email=f"note_{uid}{suffix}@test.local",
        password_hash=get_password_hash("password123"),
    )


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def test_extract_note_metadata_with_markdown_header_and_tags():
    raw_text = r"""# 线性代数核心笔记：特征值与特征向量
标签：#线性代数 #特征值 #矩阵分解

## 1. 核心概念
特征值与特征向量定义为 $Av = \lambda v$。

## 2. 几何意义
变换后方向不发生偏转的向量。
"""
    title, content, tags = extract_note_metadata(raw_text, fallback_title="默认标题")
    assert title == "线性代数核心笔记：特征值与特征向量"
    assert "线性代数" in tags
    assert "特征值" in tags
    assert "矩阵分解" in tags
    # 验证清理后的正文去除了冗余独立标签行
    assert "标签：" not in content
    assert "## 1. 核心概念" in content


def test_extract_note_metadata_fallback():
    raw_text = "这是一段没有标题和标签的普通学习总结内容，包含若干关键知识点。"
    title, content, tags = extract_note_metadata(raw_text, fallback_title="深度学习速记")
    assert title == "深度学习速记"
    assert tags == ["AI整理"]
    assert content == raw_text


@pytest.mark.asyncio
async def test_query_router_note_taking_keywords():
    router = QueryRouter()
    queries = [
        "帮我把这部分内容记成笔记",
        "整理笔记：注意力机制原理",
        "保存笔记：反向传播算法",
        "把上面的讨论存为笔记",
        "帮我做一份学习笔记",
    ]
    for q in queries:
        analysis = await router.analyze(q, doc_ids=["doc-1"])
        assert analysis.intent == QueryType.NOTE_TAKING, (
            f"Query '{q}' should be classified as NOTE_TAKING"
        )


@pytest.mark.asyncio
async def test_ask_question_stream_auto_saves_note(db_session: AsyncSession, monkeypatch):
    from app.services import chat_service as _cs

    # Unit test mocks rag_engine.ask_stream — pin legacy path
    monkeypatch.setattr(_cs.settings, "pipeline_v2_enabled", False, raising=False)
    user = _create_user()
    db_session.add(user)
    await db_session.commit()

    mock_note_text = """# 注意力机制学习笔记
标签：#深度学习 #Transformer #注意力机制

## 概念解析
Self-Attention 允许模型在计算表示时关注不同位置的 token。
"""

    async def mock_stream(*args, **kwargs):
        yield {"type": "intent", "intent": "note_taking", "explanation": "识别到整理并保存笔记需求"}
        yield {"type": "token", "content": mock_note_text}

    with (
        patch("app.services.chat_service.rag_engine.ask_stream", side_effect=mock_stream),
        patch(
            "app.services.chat_service._embed_text",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ),
        patch("app.services.note_service._safe_reindex", new_callable=AsyncMock),
    ):
        events = []
        async for event in chat_service.ask_question_stream(
            db=db_session,
            user=user,
            question="帮我整理注意力机制的笔记",
            document_ids=[],
        ):
            events.append(event)

    # 验证下发了 note_saved 事件
    saved_events = [e for e in events if e.get("type") == "note_saved"]
    assert len(saved_events) == 1
    note_info = saved_events[0]["note"]
    assert note_info["title"] == "注意力机制学习笔记"
    assert "Transformer" in note_info["tags"]

    # 验证数据库中确实落库了 Note
    db_note = await db_session.get(Note, note_info["id"])
    assert db_note is not None
    assert db_note.user_id == user.id
    assert "Self-Attention" in db_note.content


@pytest.mark.asyncio
async def test_manual_save_message_as_note_service(db_session: AsyncSession):
    user = _create_user()
    db_session.add(user)
    await db_session.commit()

    session = ChatSession(id=str(uuid.uuid4()), user_id=user.id, title="测试会话")
    msg = Message(
        id=str(uuid.uuid4()),
        session_id=session.id,
        role="assistant",
        content="# 操作系统核心考点：虚拟内存\n标签：#操作系统 #分页 #虚拟内存\n\n虚拟内存为每个进程提供独立的地址空间。",
    )
    db_session.add_all([session, msg])
    await db_session.commit()

    with (
        patch("app.services.note_service._safe_reindex", new_callable=AsyncMock),
    ):
        note = await chat_service.save_message_as_note(db_session, user, msg.id)

    assert note is not None
    assert note.title == "操作系统核心考点：虚拟内存"
    assert note.user_id == user.id

    # 检查消息 sources 中是否已回写 saved_note
    updated_msg = await db_session.get(Message, msg.id)
    assert updated_msg is not None
    assert updated_msg.sources is not None
    sources_data = json.loads(updated_msg.sources)
    assert "saved_note" in sources_data
    assert sources_data["saved_note"]["id"] == note.id


@pytest.mark.asyncio
async def test_manual_save_note_api_and_history_reconstruction(
    client: AsyncClient,
    db_session: AsyncSession,
):
    user1 = _create_user("1")
    user2 = _create_user("2")
    db_session.add_all([user1, user2])
    await db_session.commit()

    session = ChatSession(id=str(uuid.uuid4()), user_id=user1.id, title="数学物理方程")
    msg = Message(
        id=str(uuid.uuid4()),
        session_id=session.id,
        role="assistant",
        content="# 傅里叶变换基础\n标签：#数学 #信号与系统\n\n傅里叶变换将时域信号转换为频域表示。",
    )
    db_session.add_all([session, msg])
    await db_session.commit()

    # User 2 试图保存 User 1 的消息应被拒绝（404）
    resp2 = await client.post(
        f"/api/chat/messages/{msg.id}/save-note",
        headers=auth_headers(user2),
    )
    assert resp2.status_code == 404

    # User 1 正常保存
    with patch("app.services.note_service._safe_reindex", new_callable=AsyncMock):
        resp1 = await client.post(
            f"/api/chat/messages/{msg.id}/save-note",
            headers=auth_headers(user1),
        )
    assert resp1.status_code == 200
    res_json = resp1.json()
    assert res_json["success"] is True
    assert res_json["note"]["title"] == "傅里叶变换基础"

    # 请求历史记录，验证 MessageResp 包含 saved_note / savedNote
    history_resp = await client.get(
        f"/api/chat/history/{session.id}",
        headers=auth_headers(user1),
    )
    assert history_resp.status_code == 200
    h_data = history_resp.json()
    assert len(h_data["messages"]) == 1
    retrieved_msg = h_data["messages"][0]
    assert retrieved_msg["saved_note"] is not None
    assert retrieved_msg["saved_note"]["title"] == "傅里叶变换基础"
    assert retrieved_msg["savedNote"] is not None
