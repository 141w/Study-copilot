"""Tests for Five-Category Long-Term Memory (app/services/memory_service.py & app/api/memory.py)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import Base, MemoryItem, MemorySubject, User, _utcnow_naive
from app.services.memory_service import (
    KIND_FACT,
    KIND_INTEREST,
    KIND_PREFERENCE,
    KIND_PROFILE,
    KIND_TASK,
    ORIGIN_EXTRACTED,
    ORIGIN_MANUAL,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_PENDING,
    STATUS_SUPERSEDED,
    build_bigrams,
    compute_lexical_score,
    memory_service,
    normalize_memory_key,
    tokenize_lexical,
)


def test_tokenize_and_bigrams():
    # CJK character-level tokenization + English word preservation
    tokens = tokenize_lexical("我正在复习Python编程与数据结构！")
    assert "我" in tokens
    assert "正" in tokens
    assert "python" in tokens
    assert "编" in tokens
    assert "数" in tokens
    assert "据" in tokens
    assert "！" not in tokens

    bigrams = build_bigrams(tokens)
    assert "数据" in bigrams
    assert "结构" in bigrams
    # Python is not Han, so no python bigrams
    assert not any("python" in bg for bg in bigrams)


def test_lexical_scoring():
    query_tokens = set(tokenize_lexical("请问数据结构中的二叉树"))
    query_bigrams = set(build_bigrams(tokenize_lexical("请问数据结构中的二叉树")))

    item1_tokens = set(tokenize_lexical("学生正在主修数据结构与算法"))
    item1_bigrams = set(build_bigrams(tokenize_lexical("学生正在主修数据结构与算法")))

    item2_tokens = set(tokenize_lexical("学生喜欢吃苹果"))
    item2_bigrams = set(build_bigrams(tokenize_lexical("学生喜欢吃苹果")))

    score1 = compute_lexical_score(query_tokens, query_bigrams, item1_tokens, item1_bigrams)
    score2 = compute_lexical_score(query_tokens, query_bigrams, item2_tokens, item2_bigrams)

    assert score1 > 5.0  # matches '数据', '结构' bigrams + individual tokens
    assert score2 == 0.0


def test_normalize_key():
    assert normalize_memory_key("  User_Goal! ") == "user_goal"
    assert normalize_memory_key("目标：考研复习") == "目标_考研复习"


@pytest.mark.asyncio
async def test_memory_crud_and_supersede(db_session: AsyncSession):
    user = User(
        id="mem-u1",
        email="mem1@test.com",
        username="memuser1",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    # 1. Add profile
    p1 = await memory_service.add_item(
        user_id=user.id,
        kind=KIND_PROFILE,
        key="grade_major",
        content="计算机科学与技术大三本科生",
        db=db_session,
    )
    assert p1.status == STATUS_ACTIVE
    assert p1.kind == KIND_PROFILE

    # 2. Add item with same key -> should supersede p1
    p2 = await memory_service.add_item(
        user_id=user.id,
        kind=KIND_PROFILE,
        key="grade_major",
        content="已保研计算机软件所研究生",
        db=db_session,
    )
    assert p2.status == STATUS_ACTIVE
    assert p2.key == p1.key

    # Check p1 superseded
    await db_session.refresh(p1)
    assert p1.status == STATUS_SUPERSEDED
    assert p1.superseded_at is not None

    # Check resident block updated
    subject = await memory_service.get_or_create_subject(user.id, db_session)
    assert "已保研" in subject.block_text
    assert "本科生" not in subject.block_text


@pytest.mark.asyncio
async def test_memory_recall_resident_and_situational(db_session: AsyncSession):
    user = User(
        id="mem-u2",
        email="mem2@test.com",
        username="memuser2",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    # Add resident preference
    await memory_service.add_item(
        user_id=user.id,
        kind=KIND_PREFERENCE,
        key="code_style",
        content="偏好 Python 代码实现，解答风格言简意赅",
        db=db_session,
    )

    # Add situational fact (related to operating systems)
    await memory_service.add_item(
        user_id=user.id,
        kind=KIND_FACT,
        key="os_exam",
        content="期末操作系统课程考试定于12月25日",
        db=db_session,
    )

    # Add another irrelevant fact
    await memory_service.add_item(
        user_id=user.id,
        kind=KIND_FACT,
        key="hobby",
        content="每周六下午打羽毛球",
        db=db_session,
    )

    # Query matching operating systems
    recall1 = await memory_service.recall(user.id, "操作系统进程调度的原理", db=db_session)
    assert recall1.enabled is True
    assert not recall1.is_empty()
    assert "言简意赅" in recall1.prompt_envelope
    assert "操作系统课程考试" in recall1.prompt_envelope
    assert "羽毛球" not in recall1.prompt_envelope  # Irrelevant filtered out!


@pytest.mark.asyncio
async def test_pending_isolation_and_confirmation(db_session: AsyncSession):
    """Pending system-inferred memories must NOT enter prompt until confirmed."""
    user = User(
        id="mem-u3",
        email="mem3@test.com",
        username="memuser3",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    # System extracted memory (pending)
    pending_item = await memory_service.add_item(
        user_id=user.id,
        kind=KIND_PROFILE,
        key="inferred_role",
        content="疑似正在备战全国电子设计竞赛",
        origin=ORIGIN_EXTRACTED,
        status=STATUS_PENDING,
        db=db_session,
    )

    # Resident block and prompt should NOT contain pending item
    subject = await memory_service.get_or_create_subject(user.id, db_session)
    assert "电子设计竞赛" not in subject.block_text

    recall = await memory_service.recall(user.id, "电子设计竞赛怎么准备", db=db_session)
    assert "电子设计竞赛" not in recall.prompt_envelope

    # Now user confirms it in management panel
    confirmed = await memory_service.confirm_pending(user.id, pending_item.id, db=db_session)
    assert confirmed.status == STATUS_ACTIVE

    # Now resident block and recall contain it!
    recall_after = await memory_service.recall(user.id, "电子设计竞赛怎么准备", db=db_session)
    assert "电子设计竞赛" in recall_after.prompt_envelope


@pytest.mark.asyncio
async def test_memory_archive_and_search(db_session: AsyncSession):
    user = User(
        id="mem-u4",
        email="mem4@test.com",
        username="memuser4",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    item = await memory_service.add_item(
        user_id=user.id,
        kind=KIND_TASK,
        key="task_math",
        content="正在研读考研高等数学第七章多元微分",
        db=db_session,
    )

    search_res = await memory_service.search(user.id, "高等数学微分", db=db_session)
    assert search_res["available"] is True
    assert len(search_res["items"]) >= 1
    assert search_res["items"][0]["key"] == "task_math"

    # Archive
    archived = await memory_service.archive_item(user.id, item.id, db=db_session)
    assert archived.status == STATUS_ARCHIVED

    # Hard delete
    deleted = await memory_service.delete_item(user.id, item.id, db=db_session)
    assert deleted is True


@pytest.mark.asyncio
async def test_api_memory_endpoints(client, db_session: AsyncSession):
    from app.services.auth_service import create_access_token

    user = User(
        id="mem-api-user",
        email="memapi@test.com",
        username="memapiuser",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": user.id, "username": user.username})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. POST /api/memory
    resp = await client.post(
        "/api/memory",
        json={"kind": "preference", "content": "喜欢用 Go 和 Python", "key": "fav_lang"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    item_id = data["id"]
    assert data["kind"] == "preference"

    # 2. GET /api/memory
    resp = await client.get("/api/memory", headers=headers)
    assert resp.status_code == 200
    list_data = resp.json()
    assert len(list_data["items"]) >= 1
    assert list_data["config"]["enabled"] is True

    # 3. POST /api/memory/{id}/supersede
    resp = await client.post(f"/api/memory/{item_id}/supersede", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "superseded"

    # 4. PUT /api/memory/config
    resp = await client.put("/api/memory/config", json={"enabled": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # 5. DELETE /api/memory/{id}
    resp = await client.delete(f"/api/memory/{item_id}", headers=headers)
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"]
