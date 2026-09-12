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
    quizzes = (
        (await db_session.execute(__import__("sqlalchemy").select(Quiz).order_by(Quiz.question)))
        .scalars()
        .all()
    )
    assert len(quizzes) == 2
    assert all(q.document_id is None for q in quizzes)

    quiz_results = (
        (await db_session.execute(__import__("sqlalchemy").select(QuizResult))).scalars().all()
    )
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


async def test_webhook_rejects_missing_classroom_id(client, monkeypatch):
    """Signature ok but empty classroom_id → 422 (payload validation after auth)."""
    from app.services import classroom_service as svc

    secret = "whsec-empty-id"
    monkeypatch.setattr(svc.settings, "classroom_webhook_secret", secret, raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)

    body = json.dumps(
        {"event": "classroom_completed", "classroom_id": "", "title": "x"}
    ).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    resp = await client.post(
        "/api/classroom/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Classroom-Signature": sig},
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


async def test_webhook_signed_callback_updates_placeholder(
    db_session, local_user, client, monkeypatch
):
    """完整闭环：提交占位课 → completed 回调原地更新同一门课（非重复建课）。"""
    from app.services import classroom_service as svc
    from app.services.course_service import create_course_space

    secret = "whsec"
    monkeypatch.setattr(svc.settings, "classroom_webhook_secret", secret, raising=False)
    monkeypatch.setattr(svc.settings, "debug", False, raising=False)

    # 提交侧占位课
    placeholder = await create_course_space(
        db_session,
        local_user,
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


async def test_webhook_orphan_classroom_id_rejected(
    db_session, local_user, client, monkeypatch
):
    """Unowned classroom_id must NOT be attached to the first user (multi-tenant IDOR)."""
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
    assert resp.status_code == 404


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

    mock_poll = AsyncMock(
        return_value={
            "status": "running",
            "step": "generating_scenes",
            "progress": 0.6,
            "message": "正在生成场景课件...",
            "scenes_generated": 3,
            "total_scenes": 5,
            "done": False,
        }
    )
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


async def test_get_classroom_status_auto_syncs_placeholder(
    db_session, local_user, client, monkeypatch
):
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
        db_session,
        local_user,
        name="离散数学（生成中）",
        description=json.dumps(
            {"classroom_pending": True, "job_id": job_id, "classroom_id": "cls-99"}
        ),
        color="#409EFF",
    )
    await db_session.commit()

    mock_poll = AsyncMock(
        return_value={
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
        }
    )
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


async def test_create_classroom_unreachable_engine_raises_error(
    db_session, local_user, client, monkeypatch
):
    """当 OpenMAIC 外部课堂引擎不可达时，返回明确错误引导启动服务，拒绝简陋本地 mock 课件。"""
    from app.db import Document
    from app.services import classroom_service as svc
    from app.utils.auth import create_access_token

    monkeypatch.setattr(svc.settings, "classroom_enabled", True, raising=False)
    monkeypatch.setattr(svc.settings, "classroom_base_url", "http://127.0.0.1:19999", raising=False)
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

    resp = await client.post(
        "/api/classroom/generate",
        json={"doc_ids": [doc.id], "requirement": "测试生成"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (403, 502)
    data = resp.json()
    assert "OpenMAIC" in data["detail"] or "未启动" in data["detail"] or "连接" in data["detail"]


async def test_create_classroom_successful_openmaic_submission(
    db_session, local_user, client, monkeypatch
):
    """当 OpenMAIC 正常响应时，成功创建占位课程并返回任务信息。"""
    from unittest.mock import AsyncMock

    from sqlalchemy import select

    from app.db import CourseSpace, Document
    from app.services import classroom_service as svc
    from app.utils.auth import create_access_token

    monkeypatch.setattr(svc.settings, "classroom_enabled", True, raising=False)
    monkeypatch.setattr(svc.settings, "classroom_base_url", "http://localhost:3001", raising=False)
    token = create_access_token({"sub": local_user.id, "username": local_user.username})

    doc = Document(
        id="doc-test-2",
        user_id=local_user.id,
        filename="深度学习导论.pdf",
        file_path="/tmp/dl.pdf",
        file_size=200,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()

    mock_submit = AsyncMock(
        return_value={
            "jobId": "openmaic-job-123",
            "status": "queued",
            "step": "generating_outline",
            "message": "课堂生成已排队",
            "pollUrl": "http://localhost:3001/api/generate-classroom/openmaic-job-123",
        }
    )
    monkeypatch.setattr(svc, "submit_classroom_generation", mock_submit)

    resp = await client.post(
        "/api/classroom/generate",
        json={"doc_ids": [doc.id], "requirement": "神经网络基础"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "openmaic-job-123"
    assert data["status"] == "queued"
    assert data["course_id"] is not None
    assert data["task_id"] is not None

    # 验证占位课是否写入数据库
    c_res = await db_session.execute(select(CourseSpace).where(CourseSpace.id == data["course_id"]))
    course = c_res.scalar_one_or_none()
    assert course is not None
    assert "神经网络基础" in course.name
    meta = json.loads(course.description)
    assert meta["classroom_pending"] is True
    assert meta["job_id"] == "openmaic-job-123"
    assert meta["source_doc_ids"] == [doc.id]

    # 验证 AsyncTask 写入数据库且包含必要元数据
    from app.db import AsyncTask
    t_res = await db_session.execute(select(AsyncTask).where(AsyncTask.id == data["task_id"]))
    task = t_res.scalar_one_or_none()
    assert task is not None
    assert task.task_type == "classroom_generate"
    assert task.status == "pending"
    task_res = json.loads(task.result) if isinstance(task.result, str) else task.result
    assert task_res["job_id"] == "openmaic-job-123"
    assert task_res["course_id"] == data["course_id"]


async def test_task_worker_classroom_generate_success(db_session, local_user, monkeypatch):
    """测试 TaskWorker 处理 classroom_generate 任务的轮询与成功完成流程。"""
    from unittest.mock import AsyncMock

    from app.core.task_worker import TaskJob, _run_classroom_generate
    from app.services import classroom_service as svc

    poll_responses = [
        {
            "status": "running",
            "progress": 45,
            "step": "generating_scenes",
            "message": "正在生成分幕场景 2/5",
            "done": False,
        },
        {
            "status": "completed",
            "progress": 100,
            "step": "completed",
            "message": "课堂生成完成",
            "done": True,
            "result": {"classroomId": "cr-final-456"},
        },
    ]
    mock_poll = AsyncMock(side_effect=poll_responses)
    mock_sync = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(svc, "poll_generation_status", mock_poll)
    monkeypatch.setattr(svc, "sync_completed_classroom_job", mock_sync)

    job = TaskJob(
        task_id="task-cr-test",
        user_id=local_user.id,
        task_type="classroom_generate",
        payload={"job_id": "openmaic-job-456", "course_id": "course-test-123", "title": "测试课堂"},
    )

    # 预设一条 AsyncTask 记录
    from app.db import AsyncTask
    task_record = AsyncTask(
        id="task-cr-test",
        user_id=local_user.id,
        task_type="classroom_generate",
        status="pending",
        progress=0.0,
        result=json.dumps(job.payload),
    )
    db_session.add(task_record)
    await db_session.commit()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await _run_classroom_generate(job, db_session)

    assert res["classroom_id"] == "cr-final-456"
    assert res["course_id"] == "course-test-123"
    assert "/courses/course-test-123/classroom" in res["url"]
    assert mock_sync.await_count == 1


async def test_task_worker_classroom_stall_watchdog(db_session, local_user, monkeypatch):
    """测试当课堂生成长时间无进度更新（停滞）时，正确触发 TimeoutError。"""
    from unittest.mock import AsyncMock

    from app.core import task_worker
    from app.services import classroom_service as svc

    # 模拟持续无进展的同一状态
    stall_response = {
        "status": "running",
        "progress": 50,
        "step": "generating_scenes",
        "message": "停滞在某一步骤",
        "scenes_generated": 2,
        "done": False,
    }
    mock_poll = AsyncMock(return_value=stall_response)
    monkeypatch.setattr(svc, "poll_generation_status", mock_poll)
    monkeypatch.setattr(task_worker, "CLASSROOM_STALL_TIMEOUT_SEC", 0.01)

    job = task_worker.TaskJob(
        task_id="task-stall-test",
        user_id=local_user.id,
        task_type="classroom_generate",
        payload={"job_id": "openmaic-job-stall", "course_id": "course-1", "title": "停滞测试"},
    )

    from app.db import AsyncTask
    task_record = AsyncTask(
        id="task-stall-test",
        user_id=local_user.id,
        task_type="classroom_generate",
        status="pending",
        progress=0.0,
        result=json.dumps(job.payload),
    )
    db_session.add(task_record)
    await db_session.commit()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(TimeoutError) as exc_info:
            await task_worker._run_classroom_generate(job, db_session)
        assert "停滞超过" in str(exc_info.value)


async def test_execute_job_classroom_timeout_error_message(db_session, local_user, monkeypatch):
    """测试 _execute_job 对 classroom_generate 超时时返回精准的业务错误提示，而非误报 Embedding。"""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from app.core import task_worker

    job = task_worker.TaskJob(
        task_id="task-msg-test",
        user_id=local_user.id,
        task_type="classroom_generate",
        payload={"job_id": "openmaic-job-timeout", "title": "超时测试"},
    )

    from app.db import AsyncTask
    task_record = AsyncTask(
        id="task-msg-test",
        user_id=local_user.id,
        task_type="classroom_generate",
        status="pending",
        progress=0.0,
        result=json.dumps(job.payload),
    )
    db_session.add(task_record)
    await db_session.commit()

    @asynccontextmanager
    async def mock_session_local():
        yield db_session

    monkeypatch.setattr(task_worker, "AsyncSessionLocal", mock_session_local)

    async def raise_timeout(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr(task_worker, "_run_classroom_generate", raise_timeout)
    monkeypatch.setattr(task_worker, "CLASSROOM_TASK_TIMEOUT_SEC", 3600)

    await task_worker._execute_job(job)

    await db_session.refresh(task_record)
    assert task_record.status == "failed"
    assert "Embedding" not in task_record.error
    assert "AI 互动课堂生成超时" in task_record.error

