"""AI 互动课堂服务与接口回归测试。

覆盖：
1. sync_quiz_results：课堂测验（document_id=None）可落库（Quiz.document_id 已放开可空）
2. webhook 签名：fail-closed（未配密钥拒绝；配了密钥验签；DEBUG=True 放行）
3. webhook classroom_id：空值 422
4. webhook 回调原地更新占位课并同步测验
5. GET /api/classroom/{job_id}/status 轮询与双通道自愈
6. POST /api/classroom/generate 课堂生成发起
"""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from app.db import Quiz, QuizResult
from app.services import classroom_service


@pytest.fixture
async def local_user(db_session):
    from app.db import User
    from app.utils.auth import get_password_hash

    user = User(
        id="u-classroom-user",
        username="classroomuser",
        email="cr@example.com",
        password_hash=get_password_hash("x12345"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_sync_quiz_results_with_null_document_id(db_session, local_user):
    """课堂来源测验无 document_id，INSERT 不再 IntegrityError。"""
    results = await classroom_service.sync_quiz_results(
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
    assert all(q.document_id is None for q in quizzes)

    quiz_results = (await db_session.execute(
        __import__("sqlalchemy").select(QuizResult)
    )).scalars().all()
    assert len(quiz_results) == 2
    assert quiz_results[0].user_id == local_user.id


async def test_sync_quiz_results_empty_list(db_session, local_user):
    assert await classroom_service.sync_quiz_results(db_session, local_user, []) == 0


# ── webhook 签名 fail-closed ────────────────────────────────────────────────


def test_verify_signature_rejects_when_secret_unset():
    """未配置密钥且非 DEBUG：拒绝。"""
    with (
        patch.object(classroom_service.settings, "classroom_webhook_secret", ""),
        patch.object(classroom_service.settings, "debug", False),
    ):
        assert classroom_service.verify_webhook_signature(b"{}", "any") is False
        assert classroom_service.verify_webhook_signature(b"{}", None) is False


def test_verify_signature_allows_in_debug_mode():
    """未配置密钥但 DEBUG=True：本地开发放行。"""
    with (
        patch.object(classroom_service.settings, "classroom_webhook_secret", ""),
        patch.object(classroom_service.settings, "debug", True),
    ):
        assert classroom_service.verify_webhook_signature(b"{}", "any") is True


def test_verify_signature_valid_hmac():
    secret = "s3cret"
    body = b'{"event": "classroom_completed"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    with (
        patch.object(classroom_service.settings, "classroom_webhook_secret", secret),
        patch.object(classroom_service.settings, "debug", False),
    ):
        assert classroom_service.verify_webhook_signature(body, sig) is True
        assert classroom_service.verify_webhook_signature(b"tampered", sig) is False
        assert classroom_service.verify_webhook_signature(body, None) is False


# ── webhook 端点：classroom_id 空值与匹配 ────────────────────────────────────


async def test_webhook_rejects_missing_classroom_id(client):
    resp = await client.post(
        "/api/classroom/webhook",
        json={"event": "classroom_completed", "classroom_id": "", "title": "x"},
    )
    assert resp.status_code == 422


async def test_webhook_classroom_mode_requires_secret_in_prod(client, monkeypatch):
    """生产模式（debug=False、无密钥）下 webhook 直接被签名验证拒绝。"""
    from app.services import classroom_service as svc

    monkeypatch.setattr(svc.settings, "classroom_webhook_secret", "", raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)
    resp = await client.post(
        "/api/classroom/webhook",
        json={"event": "classroom_completed", "classroom_id": "cls-1", "title": "x"},
    )
    assert resp.status_code == 401


async def test_webhook_signed_callback_updates_placeholder(db_session, local_user, client, monkeypatch):
    """完整闭环：提交占位课 → completed 回调原地更新同一门课（非重复建课）。"""
    from app.services import classroom_service as svc
    from app.services.course_service import create_course_space

    secret = "whsec"
    monkeypatch.setattr(svc.settings, "classroom_webhook_secret", secret, raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)

    # 提交侧占位课
    placeholder = await create_course_space(
        db_session, local_user,
        name="线代入门（生成中）",
        description=json.dumps({"classroom_pending": True, "classroom_id": "cls-create-1"}),
        color="#409EFF",
    )
    await db_session.commit()

    payload = {
        "event": "classroom_completed",
        "classroom_id": "cls-create-1",
        "title": "线代入门互动课堂",
        "url": "http://localhost:3001/classroom/cls-create-1",
        "quiz_results": [
            {"question": "Q1", "user_answer": "A", "correct_answer": "A", "is_correct": True},
        ],
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = await client.post(
        "/api/classroom/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Classroom-Signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["result"]["course_id"] == placeholder.id
    await db_session.refresh(placeholder)
    assert placeholder.name == "线代入门互动课堂"
    meta = json.loads(placeholder.description)
    assert meta["classroom_url"] == "http://localhost:3001/classroom/cls-create-1"
    assert data["result"]["quizzes_synced"] == 1


async def test_webhook_fallback_creates_course_without_placeholder(db_session, local_user, client, monkeypatch):
    from app.services import classroom_service as svc

    secret = "whsec2"
    monkeypatch.setattr(svc.settings, "classroom_webhook_secret", secret, raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)

    payload = {
        "event": "classroom_completed",
        "classroom_id": "cls-orphan-1",
        "title": "孤儿课堂",
        "url": "http://localhost:3001/classroom/cls-orphan-1",
        "quiz_results": [],
    }
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = await client.post(
        "/api/classroom/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Classroom-Signature": sig},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── GET /api/classroom/{job_id}/status 轮询与自愈测试 ──────────────────────────


async def test_get_classroom_status_requires_classroom_enabled(client, local_user, monkeypatch):
    from app.services import classroom_service as svc
    from app.utils.auth import create_access_token

    monkeypatch.setattr(svc.settings, "classroom_enabled", False, raising=False)
    token = create_access_token({"sub": local_user.id, "username": local_user.username})

    resp = await client.get(
        "/api/classroom/job-123/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_get_classroom_status_in_progress(client, local_user, monkeypatch):
    from unittest.mock import AsyncMock

    from app.services import classroom_service as svc
    from app.utils.auth import create_access_token

    monkeypatch.setattr(svc.settings, "classroom_enabled", True, raising=False)
    monkeypatch.setattr(svc.settings, "classroom_base_url", "http://localhost:3001", raising=False)
    token = create_access_token({"sub": local_user.id, "username": local_user.username})

    mock_poll = AsyncMock(return_value={
        "status": "running",
        "step": "generating_scenes",
        "progress": 0.6,
        "message": "正在生成场景课件...",
        "scenes_generated": 3,
        "total_scenes": 5,
        "done": False,
    })
    monkeypatch.setattr(svc, "poll_generation_status", mock_poll)

    resp = await client.get(
        "/api/classroom/job-progress-1/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["step"] == "generating_scenes"
    assert data["progress"] == 0.6
    assert data["done"] is False
    assert data["scenes_generated"] == 3


async def test_get_classroom_status_auto_syncs_placeholder(db_session, local_user, client, monkeypatch):
    """验证当轮询发现任务完成时，双通道自愈逻辑会自动更新占位课并同步测验。"""
    from unittest.mock import AsyncMock

    from app.services import classroom_service as svc
    from app.services.course_service import create_course_space
    from app.utils.auth import create_access_token

    monkeypatch.setattr(svc.settings, "classroom_enabled", True, raising=False)
    monkeypatch.setattr(svc.settings, "classroom_base_url", "http://localhost:3001", raising=False)
    token = create_access_token({"sub": local_user.id, "username": local_user.username})

    job_id = "job-auto-sync-99"
    placeholder = await create_course_space(
        db_session, local_user,
        name="离散数学（生成中）",
        description=json.dumps({"classroom_pending": True, "job_id": job_id, "classroom_id": "cls-99"}),
        color="#409EFF",
    )
    await db_session.commit()

    mock_poll = AsyncMock(return_value={
        "status": "succeeded",
        "step": "completed",
        "progress": 1.0,
        "message": "生成完毕",
        "done": True,
        "result": {
            "classroomId": "cls-99",
            "url": "http://localhost:3001/classroom/cls-99",
            "title": "离散数学：图论基础",
            "quiz_results": [
                {
                    "question": "什么是欧拉图？",
                    "user_answer": "存在欧拉回路",
                    "correct_answer": "存在欧拉回路",
                    "is_correct": True,
                }
            ],
        },
    })
    monkeypatch.setattr(svc, "poll_generation_status", mock_poll)

    resp = await client.get(
        f"/api/classroom/{job_id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["status"] == "succeeded"
    assert data["sync_result"] is not None
    assert data["sync_result"]["course_id"] == placeholder.id
    assert data["sync_result"]["quizzes_synced"] == 1

    await db_session.refresh(placeholder)
    assert placeholder.name == "离散数学：图论基础"
    meta = json.loads(placeholder.description)
    assert meta["classroom_url"] == "http://localhost:3001/classroom/cls-99"


async def test_create_classroom_local_fallback(db_session, local_user, client, monkeypatch):
    """当外部课堂引擎不可达时，能够自动调用本地 course_generator 保底创建课程。"""
    from app.db import Document
    from app.services import classroom_service as svc
    from app.utils.auth import create_access_token

    monkeypatch.setattr(svc.settings, "classroom_enabled", True, raising=False)
    monkeypatch.setattr(svc.settings, "classroom_base_url", "http://localhost:9999", raising=False)
    token = create_access_token({"sub": local_user.id, "username": local_user.username})

    # 创建测试文档
    doc = Document(
        id="doc-test-1",
        user_id=local_user.id,
        filename="测试文档.txt",
        file_path="/tmp/test.txt",
        file_size=100,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()

    from unittest.mock import AsyncMock

    with patch("app.core.course_generator.generate_course", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "outline": {"title": "测试生成课程", "sections": []},
            "quizzes": [],
        }
        resp = await client.post(
            "/api/classroom/generate",
            json={"doc_ids": [doc.id], "requirement": "测试生成"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "succeeded"
        assert data["job_id"].startswith("local-")
        assert data["course_id"] is not None
