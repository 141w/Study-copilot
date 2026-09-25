"""5.5 断线续流：incomplete 落库、history 暴露、resume 端点。"""

import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatSession, Message, User
from app.services import chat_service
from app.services.auth_service import create_access_token, get_password_hash


async def _user(db: AsyncSession, username: str = "resume_user") -> User:
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


def _auth(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


async def _seed_incomplete_message(
    db: AsyncSession, user: User, *, partial: str = "光合作用发生在"
) -> tuple[str, str]:
    session_id = str(uuid.uuid4())
    db.add(ChatSession(id=session_id, user_id=user.id, title="resume sess"))
    await db.commit()
    msg_id = str(uuid.uuid4())
    sources = json.dumps(
        {
            "sources": [],
            "incomplete": True,
            "question": "光合作用的场所是什么？",
            "document_ids": [],
            "mode": "fast",
            "session_id": session_id,
            "partial": partial,
        },
        ensure_ascii=False,
    )
    db.add(
        Message(
            id=msg_id,
            session_id=session_id,
            role="assistant",
            content=partial,
            sources=sources,
        )
    )
    await db.commit()
    return session_id, msg_id


@pytest.mark.asyncio
async def test_interrupted_stream_persists_partial_with_incomplete_flag(db_session):
    user = await _user(db_session, "gen_exit_user")

    async def fake_stream(*a, **kw) -> AsyncIterator[dict]:
        yield {"type": "token", "content": "部分回答"}
        yield {"type": "token", "content": "更多"}
        yield {"type": "done"}

    with patch.object(chat_service, "get_llm_config_with_secret", return_value={}):
        with patch.object(chat_service.settings, "pipeline_v2_enabled", False):
            with patch.object(chat_service.rag_engine, "ask_stream", side_effect=fake_stream):
                gen = chat_service.ask_question_stream(
                    db_session, user, "测试问题", [], None, None, mode="fast"
                )
                token_count = 0
                async for ev in gen:
                    if ev.get("type") == "token":
                        token_count += 1
                        if token_count >= 2:
                            break
                # 模拟客户端断开：aclose 把 GeneratorExit 注入生成器
                await gen.aclose()

    result = await db_session.execute(
        select(Message).where(Message.role == "assistant")
    )
    msgs = list(result.scalars().all())
    assert msgs, "中断后必须落库部分回答"
    blob = json.loads(msgs[-1].sources)
    assert blob.get("incomplete") is True
    assert blob.get("partial") == "部分回答更多"
    assert blob.get("question") == "测试问题"


@pytest.mark.asyncio
async def test_history_exposes_incomplete_flag(client: AsyncClient, db_session):
    user = await _user(db_session, "hist_user")
    session_id, msg_id = await _seed_incomplete_message(db_session, user)

    resp = await client.get(f"/api/chat/history/{session_id}", headers=_auth(user))
    assert resp.status_code == 200
    body = resp.json()
    incomplete_msgs = [m for m in body["messages"] if m.get("incomplete")]
    assert incomplete_msgs, "history 必须暴露 incomplete 字段"
    assert incomplete_msgs[0]["id"] == msg_id


@pytest.mark.asyncio
async def test_resume_replay_from_buffer(client: AsyncClient, db_session):
    user = await _user(db_session, "buf_user")
    session_id, msg_id = await _seed_incomplete_message(db_session, user, partial="AB")

    from app.core.sse_resume import stream_resume_buffer

    buffered = stream_resume_buffer.create(str(user.id))
    # 更新 meta 指向该 buffer
    result = await db_session.execute(select(Message).where(Message.id == msg_id))
    msg = result.scalar_one()
    blob = json.loads(msg.sources)
    blob["stream_id"] = buffered.stream_id
    msg.sources = json.dumps(blob, ensure_ascii=False)
    await db_session.commit()

    stream_resume_buffer.append(buffered.stream_id, {"type": "token", "content": "CD", "id": 1})
    stream_resume_buffer.mark_finished(buffered.stream_id)

    resp = await client.post(
        f"/api/chat/messages/{msg_id}/resume?last_event_id=0", headers=_auth(user)
    )
    assert resp.status_code == 200
    assert "CD" in resp.text
    assert '"type": "done"' in resp.text or '"type":"done"' in resp.text

    await db_session.refresh(msg)
    assert json.loads(msg.sources).get("incomplete") is False
    assert "CD" in msg.content


@pytest.mark.asyncio
async def test_resume_regenerates_tail_when_no_buffer(client: AsyncClient, db_session):
    user = await _user(db_session, "regen_user")
    session_id, msg_id = await _seed_incomplete_message(db_session, user, partial="前半段")

    async def fake_chat_stream(self, messages, **kw):
        yield "后半段续写"

    with patch("app.core.llm.LLM.chat_stream", new=fake_chat_stream):
        with patch.object(chat_service, "get_llm_config_with_secret", return_value={}):
            resp = await client.post(f"/api/chat/messages/{msg_id}/resume", headers=_auth(user))

    assert resp.status_code == 200
    assert "后半段续写" in resp.text
    assert "resume_mode" in resp.text

    result = await db_session.execute(select(Message).where(Message.id == msg_id))
    msg = result.scalar_one()
    assert json.loads(msg.sources).get("incomplete") is False
    assert "后半段续写" in msg.content


@pytest.mark.asyncio
async def test_resume_rejects_other_users(client: AsyncClient, db_session):
    owner = await _user(db_session, "owner_u")
    attacker = await _user(db_session, "attacker_u")
    _, msg_id = await _seed_incomplete_message(db_session, owner)

    resp = await client.post(f"/api/chat/messages/{msg_id}/resume", headers=_auth(attacker))
    assert resp.status_code == 404
