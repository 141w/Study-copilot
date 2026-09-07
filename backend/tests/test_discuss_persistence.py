"""Tests for multi-persona discussion database persistence and history reconstruction."""

import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatSession, Message, User
from app.services.auth_service import create_access_token, get_password_hash


async def create_test_user(db: AsyncSession, username: str = "disc_user") -> User:
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash=get_password_hash("password123"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


async def mock_discuss_generator(*args, **kwargs) -> AsyncIterator[dict]:
    """Mock discussion generator yielding standard multi-turn and summary events."""
    yield {
        "type": "persona_start",
        "persona": "苏老师",
        "avatar": "User",
        "color": "#6366f1",
        "turn": 1,
    }
    yield {
        "type": "persona_chunk",
        "persona": "苏老师",
        "delta": "我们首先需要明确核心概念。",
    }
    yield {
        "type": "persona_speak",
        "persona": "苏老师",
        "avatar": "User",
        "color": "#6366f1",
        "content": "我们首先需要明确核心概念。",
        "turn": 1,
    }
    yield {
        "type": "summary_start",
    }
    yield {
        "type": "summary_chunk",
        "delta": "核心共识是概念第一。",
    }
    yield {
        "type": "summary",
        "content": "核心共识是概念第一。",
    }
    yield {
        "type": "done",
    }


@pytest.mark.asyncio
async def test_discuss_creates_session_and_persists_messages(
    client: AsyncClient, db_session: AsyncSession
):
    """测试多角色讨论自动创建会话、保存用户消息与讨论成果到数据库。"""
    user = await create_test_user(db_session, "persist_user1")
    headers = auth_headers(user)

    payload = {
        "question": "什么是事件驱动架构？",
        "personas": [
            {"role": "teacher", "name": "苏老师"},
        ],
        "max_turns": 1,
    }

    with patch("app.core.persona_discussion.discuss", side_effect=mock_discuss_generator):
        res = await client.post("/api/chat/discuss", json=payload, headers=headers)
        assert res.status_code == 200
        text = res.text

        # 验证首包下发了 session 事件
        assert 'data: {"type": "session"' in text
        assert "session_id" in text

        # 解析下发的 session_id
        session_id = None
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    if ev.get("type") == "session":
                        session_id = ev.get("session_id")
                        break
                except Exception:
                    pass

        assert session_id is not None

        # 检查数据库中的 ChatSession
        sess_res = await db_session.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = sess_res.scalar_one_or_none()
        assert session is not None
        assert session.user_id == user.id
        assert session.title == "什么是事件驱动架构？"

        # 检查数据库中的 Message 记录
        msg_res = await db_session.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
        )
        messages = list(msg_res.scalars().all())
        assert len(messages) == 2

        # 第一条是用户提问
        user_msg = messages[0]
        assert user_msg.role == "user"
        assert user_msg.content == "什么是事件驱动架构？"

        # 第二条是多角色讨论成果
        disc_msg = messages[1]
        assert disc_msg.role == "discussion"
        assert "苏老师" in disc_msg.content
        assert "核心共识是概念第一。" in disc_msg.content
        assert disc_msg.sources is not None

        # 解析 sources JSON 元数据
        meta = json.loads(disc_msg.sources)
        assert meta["type"] == "discussion"
        assert len(meta["discussion_turns"]) == 1
        assert meta["discussion_turns"][0]["persona"] == "苏老师"
        assert meta["summary"] == "核心共识是概念第一。"


@pytest.mark.asyncio
async def test_get_history_reconstructs_discussion(
    client: AsyncClient, db_session: AsyncSession
):
    """测试获取历史会话时，能够正确解析并还原 discussionTurns 和 summary。"""
    user = await create_test_user(db_session, "persist_user2")
    headers = auth_headers(user)

    payload = {
        "question": "什么是反应式编程？",
        "personas": [
            {"role": "teacher", "name": "苏老师"},
        ],
        "max_turns": 1,
    }

    session_id = None
    with patch("app.core.persona_discussion.discuss", side_effect=mock_discuss_generator):
        res = await client.post("/api/chat/discuss", json=payload, headers=headers)
        assert res.status_code == 200
        for line in res.text.split("\n"):
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    if ev.get("type") == "session":
                        session_id = ev.get("session_id")
                        break
                except Exception:
                    pass

    assert session_id is not None

    # 请求历史记录端点
    hist_res = await client.get(f"/api/chat/history/{session_id}", headers=headers)
    assert hist_res.status_code == 200
    hist_data = hist_res.json()

    assert hist_data["session_id"] == session_id
    assert len(hist_data["messages"]) == 2

    disc_msg = hist_data["messages"][1]
    assert disc_msg["role"] == "discussion"
    assert disc_msg["summary"] == "核心共识是概念第一。"
    assert disc_msg["discussionTurns"] is not None
    assert len(disc_msg["discussionTurns"]) == 1
    assert disc_msg["discussionTurns"][0]["persona"] == "苏老师"
    assert disc_msg["discussionTurns"][0]["content"] == "我们首先需要明确核心概念。"


@pytest.mark.asyncio
async def test_discuss_in_existing_session(
    client: AsyncClient, db_session: AsyncSession
):
    """测试指定 session_id 时，讨论追加到既有会话中而不重复创建会话。"""
    user = await create_test_user(db_session, "persist_user3")
    headers = auth_headers(user)

    # 1. 先发起第一轮讨论
    payload1 = {
        "question": "第一轮问题",
        "personas": [{"role": "teacher", "name": "苏老师"}],
        "max_turns": 1,
    }

    session_id = None
    with patch("app.core.persona_discussion.discuss", side_effect=mock_discuss_generator):
        res1 = await client.post("/api/chat/discuss", json=payload1, headers=headers)
        assert res1.status_code == 200
        for line in res1.text.split("\n"):
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    if ev.get("type") == "session":
                        session_id = ev.get("session_id")
                        break
                except Exception:
                    pass

    assert session_id is not None

    # 2. 携带同一个 session_id 发起第二轮研讨
    payload2 = {
        "question": "第二轮追问",
        "personas": [{"role": "teacher", "name": "苏老师"}],
        "max_turns": 1,
        "session_id": session_id,
    }

    with patch("app.core.persona_discussion.discuss", side_effect=mock_discuss_generator):
        res2 = await client.post("/api/chat/discuss", json=payload2, headers=headers)
        assert res2.status_code == 200

    # 3. 验证同一个 session_id 下共有 4 条消息（user, discussion, user, discussion）
    hist_res = await client.get(f"/api/chat/history/{session_id}", headers=headers)
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert len(hist_data["messages"]) == 4
    roles = [m["role"] for m in hist_data["messages"]]
    assert roles == ["user", "discussion", "user", "discussion"]

