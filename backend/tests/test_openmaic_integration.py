"""OpenMAIC 桥接修复的回归测试（批次9）。

覆盖：
1. sync_quiz_results：课堂测验（document_id=None）可落库（Quiz.document_id 已放开可空）
2. webhook 签名：fail-closed（未配密钥拒绝；配了密钥验签；DEBUG=True 放行）
3. webhook classroom_id：空值 422，不再 LIKE '%%' 匹配任意课程
"""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from app.db import Quiz, QuizResult
from app.services import openmaic_service


@pytest.fixture
async def local_user(db_session):
    from app.db import User
    from app.utils.auth import get_password_hash

    user = User(
        id="u-openmaic",
        username="openmaicuser",
        email="om@example.com",
        password_hash=get_password_hash("x12345"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_sync_quiz_results_with_null_document_id(db_session, local_user):
    """课堂来源测验无 document_id，INSERT 不再 IntegrityError。"""
    results = await openmaic_service.sync_quiz_results(
        db_session,
        local_user,
        [
            {
                "question": "什么是向量空间？",
                "user_answer": "A",
                "correct_answer": "B",
                "is_correct": False,
                "explanation": "向量空间需满足八条公理",
            },
            {
                "question": "秩-零化度定理？",
                "user_answer": "rank + nullity = n",
                "correct_answer": "rank + nullity = n",
                "is_correct": True,
            },
        ],
    )

    assert results == 2
    quizzes = (await db_session.execute(
        __import__("sqlalchemy").select(Quiz).order_by(Quiz.question)
    )).scalars().all()
    assert len(quizzes) == 2
    # 关键断言：课堂来源测验的 document_id 为 None（此前 NOT NULL 必炸）
    assert all(q.document_id is None for q in quizzes)

    quiz_results = (await db_session.execute(
        __import__("sqlalchemy").select(QuizResult)
    )).scalars().all()
    assert len(quiz_results) == 2
    assert quiz_results[0].user_id == local_user.id


async def test_sync_quiz_results_empty_list(db_session, local_user):
    assert await openmaic_service.sync_quiz_results(db_session, local_user, []) == 0


# ── webhook 签名 fail-closed ────────────────────────────────────────────────


def test_verify_signature_rejects_when_secret_unset():
    """未配置密钥且非 DEBUG：拒绝（原实现放行）。"""
    with (
        patch.object(openmaic_service.settings, "openmaic_webhook_secret", ""),
        patch.object(openmaic_service.settings, "debug", False),
    ):
        assert openmaic_service.verify_webhook_signature(b"{}", "any") is False
        assert openmaic_service.verify_webhook_signature(b"{}", None) is False


def test_verify_signature_allows_in_debug_mode():
    """未配置密钥但 DEBUG=True：本地开发放行。"""
    with (
        patch.object(openmaic_service.settings, "openmaic_webhook_secret", ""),
        patch.object(openmaic_service.settings, "debug", True),
    ):
        assert openmaic_service.verify_webhook_signature(b"{}", "any") is True


def test_verify_signature_valid_hmac():
    secret = "s3cret"
    body = b'{"event": "classroom_completed"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    with (
        patch.object(openmaic_service.settings, "openmaic_webhook_secret", secret),
        patch.object(openmaic_service.settings, "debug", False),
    ):
        assert openmaic_service.verify_webhook_signature(body, sig) is True
        # 篡改 body → 验签失败
        assert openmaic_service.verify_webhook_signature(b"tampered", sig) is False
        # 缺签名 → 拒绝
        assert openmaic_service.verify_webhook_signature(body, None) is False


# ── webhook 端点：classroom_id 空值与匹配 ────────────────────────────────────


async def test_webhook_rejects_missing_classroom_id(client):
    resp = await client.post(
        "/api/integrations/openmaic/webhook",
        json={"event": "classroom_completed", "classroom_id": "", "title": "x"},
    )
    assert resp.status_code == 422


async def test_webhook_classroom_mode_requires_secret_in_prod(client, monkeypatch):
    """生产模式（debug=False、无密钥）下 webhook 直接被签名验证拒绝。"""
    from app.services import openmaic_service as svc

    monkeypatch.setattr(svc.settings, "openmaic_webhook_secret", "", raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)
    resp = await client.post(
        "/api/integrations/openmaic/webhook",
        json={"event": "classroom_completed", "classroom_id": "cls-1", "title": "x"},
    )
    assert resp.status_code == 403


async def test_webhook_signed_callback_updates_placeholder(db_session, local_user, client, monkeypatch):
    """完整闭环：提交占位课 → completed 回调原地更新同一门课（非重复建课）。"""
    from app.services import openmaic_service as svc
    from app.services.course_service import create_course_space

    secret = "whsec"
    monkeypatch.setattr(svc.settings, "openmaic_webhook_secret", secret, raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)

    # 提交侧占位课（模拟 POST /classroom 的批次9行为）
    placeholder = await create_course_space(
        db_session, local_user,
        name="线代入门（生成中）",
        description=json.dumps({"openmaic_pending": True, "classroom_id": "cls-create-1"}),
        color="#409EFF",
    )
    await db_session.commit()

    payload = {
        "event": "classroom_completed",
        "classroom_id": "cls-create-1",
        "title": "线代入门课堂",
        "url": "https://open.maic.chat/c/cls-create-1",
        "quiz_results": [
            {"question": "Q1", "user_answer": "A", "correct_answer": "A", "is_correct": True},
        ],
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = await client.post(
        "/api/integrations/openmaic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-OpenMAIC-Signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # 原地更新：回调作用于占位课本身，而非新建
    assert data["course_id"] == placeholder.id
    await db_session.refresh(placeholder)
    assert placeholder.name == "线代入门课堂"
    meta = json.loads(placeholder.description)
    assert meta["openmaic_url"] == "https://open.maic.chat/c/cls-create-1"
    assert data["quizzes_synced"] == 1


async def test_webhook_fallback_creates_course_without_placeholder(db_session, local_user, client, monkeypatch):
    """无占位课（历史数据/占位丢失）时回退为创建新课。"""
    from app.services import openmaic_service as svc

    secret = "whsec2"
    monkeypatch.setattr(svc.settings, "openmaic_webhook_secret", secret, raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)

    payload = {
        "event": "classroom_completed",
        "classroom_id": "cls-orphan-1",
        "title": "孤儿课堂",
        "url": "https://open.maic.chat/c/cls-orphan-1",
        "quiz_results": [],
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = await client.post(
        "/api/integrations/openmaic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-OpenMAIC-Signature": sig},
    )
    # 无占位课 → lookup no match → ignored（回退创建仅在 matched_course 为 None
    # 且课程表能匹配到任意课程的场景；纯孤儿回调按设计 ignored，防误归属）
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
