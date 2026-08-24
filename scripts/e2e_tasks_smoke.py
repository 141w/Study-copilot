#!/usr/bin/env python3
"""E2E smoke: async task pipeline（P2-3 验证）。

链路：注册/登录 → 上传文档(processing) → 后台 worker 处理 → 任务状态流转
      (pending→running→completed) → 文档变 ready → 清理删除。

用法：
    cd backend && conda activate study-c
    python ../scripts/e2e_tasks_smoke.py [base_url]
    # base_url 默认 http://localhost:8000

退出码：0=全部通过，1=失败（打印具体断言错误）。
"""

import sys
import time
import uuid

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
POLL_TIMEOUT_SEC = 90
POLL_INTERVAL_SEC = 1.0


def step(name: str) -> None:
    print(f"\n▶ {name}", flush=True)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}", flush=True)


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    suffix = uuid.uuid4().hex[:8]

    # ── 0. 健康检查 ──────────────────────────────────────────────
    step("0. 健康检查 /health")
    health = client.get("/health")
    health.raise_for_status()
    assert health.json().get("status") == "healthy", health.text
    ok("backend healthy")

    # ── 1. 注册 + 登录 ───────────────────────────────────────────
    step("1. 注册测试用户并登录")
    reg = client.post(
        "/api/auth/register",
        json={
            "username": f"smoke_{suffix}",
            "email": f"smoke_{suffix}@example.com",
            "password": "Smoke#12345",
        },
    )
    assert reg.status_code == 200, f"register failed: {reg.status_code} {reg.text}"

    login = client.post(
        "/api/auth/login",
        data={"username": f"smoke_{suffix}", "password": "Smoke#12345"},
    )
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ok(f"user smoke_{suffix} logged in")

    try:
        # ── 2. 上传文档（应立即返回 processing + 创建后台任务）────
        step("2. 上传 .txt 文档，期待 status=processing")
        doc_text = ("Study Copilot 异步任务冒烟测试段落。用于验证任务全链路。\n" * 120)
        files = {"file": (f"smoke_{suffix}.txt", doc_text.encode("utf-8"), "text/plain")}
        up = client.post("/api/documents/upload", files=files, headers=headers)
        assert up.status_code == 200, f"upload failed: {up.status_code} {up.text}"
        doc = up.json()
        assert doc.get("id"), f"upload response missing id: {doc}"
        assert doc.get("status") == "processing", (
            f"expected processing, got: {doc.get('status')}（worker 未启动时回退同步处理属预期外）"
        )
        doc_id = doc["id"]
        ok(f"document {doc_id[:8]}… created, status=processing")

        # ── 3. 轮询 /api/tasks 观察状态流转 ──────────────────────
        step("3. 轮询任务状态直至终态")
        deadline = time.time() + POLL_TIMEOUT_SEC
        observed: dict[str, set[str]] = {}
        final_task = None

        while time.time() < deadline:
            listing = client.get(
                "/api/tasks", params={"limit": 20}, headers=headers
            )
            listing.raise_for_status()
            # 宽松匹配：取该用户最新的 document_process 任务（列表按 created_at 倒序）
            tasks = [
                t
                for t in listing.json().get("tasks", [])
                if t.get("task_type") == "document_process"
            ]
            for t in tasks:
                observed.setdefault(t["id"], set()).add(t["status"])

            terminal = [t for t in tasks if t.get("status") in ("completed", "failed")]
            if terminal:
                final_task = terminal[0]
                break
            time.sleep(POLL_INTERVAL_SEC)

        assert final_task is not None, (
            f"timeout {POLL_TIMEOUT_SEC}s waiting for terminal task state; observed={observed}"
        )
        for tid, statuses in observed.items():
            ok(f"task {tid[:8]}… 状态流转: {' → '.join(statuses)}")
        assert final_task["status"] == "completed", (
            f"task failed: {final_task.get('error')}"
        )
        ok(f"task completed, result={final_task.get('result')}")

        # ── 4. 验证文档已变 ready ────────────────────────────────
        step("4. 验证文档状态变为 ready")
        docs = client.get("/api/documents", headers=headers)
        docs.raise_for_status()
        target = next((d for d in docs.json() if d.get("id") == doc_id), None)
        assert target is not None, "uploaded document missing from list"
        assert target.get("status") == "ready", (
            f"expected ready, got: {target.get('status')}"
        )
        assert (target.get("chunk_count") or 0) > 0, "chunk_count should be > 0"
        ok(f"document status=ready, chunks={target.get('chunk_count')}")

    finally:
        # ── 5. 清理 ──────────────────────────────────────────────
        step("5. 清理测试文档")
        try:
            client.delete(f"/api/documents/{doc_id}", headers=headers)
            ok("document deleted")
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ cleanup skipped: {exc}")

    print("\n✅ E2E SMOKE PASS — async task pipeline verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"\n❌ E2E SMOKE FAIL: {exc}")
        sys.exit(1)
    except httpx.ConnectError as exc:
        print(f"\n❌ E2E SMOKE FAIL: cannot connect to {BASE_URL}: {exc}")
        sys.exit(1)
