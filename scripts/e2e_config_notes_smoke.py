#!/usr/bin/env python3
"""E2E smoke: config 温度归一化 + 笔记语义搜索（Phase 12 验证）。

链路 A：POST/GET/PUT /api/config/llm 三端温度一致性
        （写入响应=十进制、读回一致、旧双形态 >1 输入兼容）
链路 B：建 2 笔记 → 语义搜索命中 → 删除后失效
        （验证 b8cba88 笔记索引与 CRUD 挂钩）

用法：
    cd backend && conda activate study-c
    python ../scripts/e2e_config_notes_smoke.py [base_url]
    # base_url 默认 http://localhost:8000

退出码：0=全部通过，1=失败（打印具体断言错误）。
"""

import sys
import uuid

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def step(name: str) -> None:
    print(f"\n▶ {name}", flush=True)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}", flush=True)


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=180.0)
    suffix = uuid.uuid4().hex[:8]
    created_note_ids: list[str] = []

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
            "username": f"smoke2_{suffix}",
            "email": f"smoke2_{suffix}@example.com",
            "password": "Smoke#12345",
        },
    )
    assert reg.status_code == 200, f"register failed: {reg.status_code} {reg.text}"
    login = client.post(
        "/api/auth/login",
        data={"username": f"smoke2_{suffix}", "password": "Smoke#12345"},
    )
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    ok(f"user smoke2_{suffix} logged in")

    try:
        # ── 2. 温度归一化：写入响应必须为十进制 ───────────────────
        step("2. POST /api/config/llm temperature=0.7 → 响应应为 0.7 而非存储原值 7")
        payload = {
            "provider": "openrouter",
            "api_key": "sk-smoke-test-key",
            "base_url": "https://openrouter.ai/api/v1",
            "model_name": "openai/gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2048,
            "embedding_model": "shibing624/text2vec-base-chinese",
            "embedding_dimension": 768,
        }
        created = client.post("/api/config/llm", json=payload, headers=headers)
        assert created.status_code == 200, f"create config failed: {created.text}"
        assert created.json()["temperature"] == 0.7, (
            f"POST 响应温度非十进制：{created.json()['temperature']}（§4.1 wart 回归）"
        )
        ok("POST 响应 temperature=0.7")

        got = client.get("/api/config/llm", headers=headers)
        assert got.status_code == 200 and got.json()["temperature"] == 0.7, got.text
        ok("GET 读回 temperature=0.7")

        step("3. PUT temperature=0.5 → 响应与读回均应为 0.5")
        put_body = dict(payload, api_key=None, temperature=0.5)  # 留空保持原 Key
        updated = client.put("/api/config/llm", json=put_body, headers=headers)
        assert updated.status_code == 200, f"update config failed: {updated.text}"
        assert updated.json()["temperature"] == 0.5, updated.text
        got2 = client.get("/api/config/llm", headers=headers)
        assert got2.json()["temperature"] == 0.5, got2.text
        ok("PUT/GET 一致 temperature=0.5")

        step("4. 旧双形态兼容：temperature=7（>1 视为已乘 10）→ 响应应为 0.7")
        legacy = client.post("/api/config/llm", json=dict(payload, temperature=7), headers=headers)
        assert legacy.status_code == 200, legacy.text
        assert abs(legacy.json()["temperature"] - 0.7) < 1e-9, (
            f"旧双形态响应异常：{legacy.json()['temperature']}"
        )
        got3 = client.get("/api/config/llm", headers=headers)
        assert abs(got3.json()["temperature"] - 0.7) < 1e-9, got3.text
        ok("legacy 7 → 响应/读回均为 0.7")

        # ── 5. 笔记语义搜索链路 ───────────────────────────────────
        step("5. 创建两篇主题不同的笔记（首次会触发向量模型加载，稍慢）")
        notes = [
            {
                "title": f"向量检索笔记_{suffix}",
                "content": "FAISS 是 Facebook AI Research 开源的高效向量相似度检索库，"
                           "支持余弦相似度与内积索引，常用于 RAG 的语义召回阶段。",
                "tag_names": ["smoke", "rag"],
            },
            {
                "title": f"出题策略笔记_{suffix}",
                "content": "自动出题应覆盖记忆、理解与应用三个认知层次；"
                           "选择题干扰项需具有合理的迷惑性，简答题判分宜采用语义裁判。",
            },
        ]
        for n in notes:
            r = client.post("/api/notes", json=n, headers=headers)
            assert r.status_code == 200, f"create note failed: {r.status_code} {r.text}"
            created_note_ids.append(r.json()["id"])
        ok(f"notes created: {len(created_note_ids)}")

        step("6. 语义搜索「向量数据库 相似度检索」→ top1 应为 FAISS 笔记")
        s1 = client.post(
            "/api/notes/search",
            json={"query": "向量数据库 相似度检索库", "top_k": 5},
            headers=headers,
        )
        assert s1.status_code == 200, f"search failed: {s1.status_code} {s1.text}"
        hits = s1.json()
        assert isinstance(hits, list) and len(hits) >= 1, f"搜索返回空：{s1.text}"
        top_title = str(hits[0].get("title", ""))
        assert "向量检索" in top_title, f"top1 命中错误：{top_title}; full={hits}"
        ok(f"top1 = {top_title} (score={hits[0].get('score')})")

        step("7. 删除 FAISS 笔记后再搜同 query → 不应再命中该笔记")
        dele = client.delete(f"/api/notes/{created_note_ids[0]}", headers=headers)
        assert dele.status_code in (200, 204), f"delete failed: {dele.text}"
        created_note_ids.remove(created_note_ids[0])
        s2 = client.post(
            "/api/notes/search",
            json={"query": "向量数据库 相似度检索库", "top_k": 5},
            headers=headers,
        )
        assert s2.status_code == 200, s2.text
        titles_after = [str(h.get("title", "")) for h in s2.json()]
        assert all("向量检索" not in t for t in titles_after), (
            f"删除后仍命中已删笔记：{titles_after}"
        )
        ok(f"删除即失效，剩余命中：{titles_after or '∅'}")

        print("\n✅ ALL PASSED（config 三端温度一致 + 笔记语义搜索链路）")
        return 0
    finally:
        # 清理本用户剩余笔记，避免污染本地数据
        for nid in created_note_ids:
            try:
                client.delete(f"/api/notes/{nid}", headers=headers)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
