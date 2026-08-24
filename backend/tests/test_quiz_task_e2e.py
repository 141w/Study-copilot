"""quiz_generate 异步任务链路集成测试（mock LLM）。

覆盖：HTTP 创建任务 → 内存队列 → worker 执行 → 服务层（LLM 打桩）
→ 题目落库 → 任务状态 pending→running→completed。

关键点：
- monkeypatch task_worker.AsyncSessionLocal 使 worker 与 API 共享同一
  测试 SQLite 引擎，避免"API 写 sqlite / worker 写 PG"的分裂；
- monkeypatch quiz_service.QuizGenerator 为假生成器，隔离真实 LLM 网络。
"""

import asyncio
import time

import pytest
from app.core import task_worker
from app.db import Quiz
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeQuizGenerator:
    """替身：按请求的数量返回固定题目，不触网。"""

    def __init__(self, llm_config=None):
        self.llm_config = llm_config

    async def generate_quizzes(
        self, context: str, choice_count: int = 3, short_answer_count: int = 2
    ) -> list[dict]:
        out: list[dict] = []
        for i in range(choice_count):
            out.append(
                {
                    "question_type": "choice",
                    "question": f"选择题{i}：下列哪项由 mock 生成？",
                    "options": ["A", "B", "C", "D"],
                    "answer": "A",
                    "explanation": "mock explanation",
                }
            )
        for i in range(short_answer_count):
            out.append(
                {
                    "question_type": "short_answer",
                    "question": f"简答题{i}：请简述 mock 的作用。",
                    "answer": "用于隔离外部依赖",
                    "explanation": "",
                }
            )
        return out


async def _wait_terminal(
    client: AsyncClient, headers: dict, task_id: str, timeout_s: float = 20.0
) -> dict:
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/tasks/{task_id}", headers=headers)
        resp.raise_for_status()
        last = resp.json()
        if last["status"] in ("completed", "failed", "cancelled"):
            return last
        await asyncio.sleep(0.2)
    raise AssertionError(f"task did not finish in {timeout_s}s: {last}")


@pytest.mark.asyncio
async def test_quiz_generate_task_full_chain(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    # ── 0. 打桩：LLM 生成器 + worker 会话工厂对齐测试引擎 ──
    monkeypatch.setattr("app.services.quiz_service.QuizGenerator", FakeQuizGenerator)
    # AsyncSession.bind 才是异步引擎本身；get_bind() 返回同步门面不可用
    monkeypatch.setattr(
        task_worker,
        "AsyncSessionLocal",
        async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False),
    )

    suffix = str(int(time.time() * 1000))[-8:]

    # ── 1. 注册 + 登录 ──
    reg = await client.post(
        "/api/auth/register",
        json={
            "username": f"qtask_{suffix}",
            "email": f"qtask_{suffix}@t.com",
            "password": "Qt#123456",
        },
    )
    assert reg.status_code == 200, reg.text
    login = await client.post(
        "/api/auth/login",
        data={"username": f"qtask_{suffix}", "password": "Qt#123456"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # ── 2. 上传文档（worker 未启动 → 同步回退，立即 ready）──
    doc_text = ("Quiz 任务链路集成测试段落，用于生成题目上下文。\n" * 100)
    up = await client.post(
        "/api/documents/upload",
        files={"file": (f"q_{suffix}.txt", doc_text.encode("utf-8"), "text/plain")},
        headers=headers,
    )
    assert up.status_code == 200, up.text
    doc = up.json()
    assert doc["status"] == "ready", doc
    doc_id = doc["id"]

    try:
        # ── 3. 启动 worker ──
        await task_worker.start_worker()

        # ── 4. 创建 quiz_generate 异步任务 ──
        created = await client.post(
            "/api/tasks",
            json={
                "task_type": "quiz_generate",
                "payload": {
                    "document_ids": [doc_id],
                    "choice_count": 2,
                    "short_answer_count": 1,
                },
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        task = created.json()
        assert task["status"] == "pending"
        task_id = task["id"]

        # ── 5. 轮询至终态并断言成功 ──
        final = await _wait_terminal(client, headers, task_id)
        assert final["status"] == "completed", final
        assert final["result"]["quiz_count"] == 3, final

        # ── 6. 题目确实落库且归属该文档 ──
        res = await db_session.execute(select(Quiz).where(Quiz.document_id == doc_id))
        rows = list(res.scalars().all())
        assert len(rows) == 3
        types = sorted(q.question_type for q in rows)
        assert types == ["choice", "choice", "short_answer"]
        assert all("mock" in (q.explanation or "") or q.answer for q in rows)
    finally:
        await task_worker.stop_worker()
        # 清理文档及其向量索引，保持测试环境干净
        try:
            await client.delete(f"/api/documents/{doc_id}", headers=headers)
        except Exception:  # noqa: BLE001
            pass
