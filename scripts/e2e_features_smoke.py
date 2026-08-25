#!/usr/bin/env python3
"""E2E smoke: 功能面真机验证（TTS / URL 导入 / LLM 全链路可选）。

无条件段：
  A. URL 导入——本地受控网页（脚本内起 HTTP 服务），避免外网不确定性
  B. TTS 语音合成——Edge TTS 免费服务；网络不通时记 SKIP 不判 FAIL

LLM 段（提供 Key 才跑，否则整段 SKIP）：
  C. chat ask 非流式直答
  D. 内容转换 8 类型逐个产出非空结果
  E. 真实出题(1 选择+1 简答) → 自答判对 / 错误选项判错 → 简答语义裁判记录

Key 注入方式（仅经环境变量，绝不打印明文）：
  export SMOKE_LLM_API_KEY=sk-xxx
  export SMOKE_LLM_BASE_URL=https://api.openai.com/v1   # 可选
  export SMOKE_LLM_MODEL=gpt-4o-mini                    # 可选

用法：
    cd backend && conda activate study-c
    python ../scripts/e2e_features_smoke.py [base_url]
退出码：0=通过（含合法 SKIP），1=失败。
"""

import asyncio
import os
import pathlib
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
ARTICLE_PORT = 8977

ARTICLE_HTML = """<!DOCTYPE html><html><head><title>向量数据库入门</title></head>
<body><article><h1>向量数据库入门</h1>
<p>向量数据库专门用于存储与检索高维向量。文本经过 Embedding 模型编码后成为
稠密向量，相似语义的文本在向量空间中距离更近。</p>
<p>FAISS 是 Meta 开源的向量检索库，支持内积与余弦相似度；HNSW 是常用的
近似最近邻图索引算法，在召回率与速度之间取得平衡。RAG 系统通常先做
语义召回，再把命中片段交给大语言模型生成答案。</p>
</article></body></html>"""


def step(name: str) -> None:
    print(f"\n▶ {name}", flush=True)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}", flush=True)


def skip(msg: str) -> None:
    print(f"  ⊘ SKIP: {msg}", flush=True)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = ARTICLE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静默访问日志
        pass


def main() -> int:
    failures = 0
    client = httpx.Client(base_url=BASE_URL, timeout=180.0, trust_env=False)
    suffix = uuid.uuid4().hex[:8]
    doc_ids: list[str] = []

    # ── 0/1 健康检查 + 登录 ──────────────────────────────────────
    step("0. 健康检查")
    r = client.get("/health")
    r.raise_for_status()
    ok("backend healthy")

    step("1. 注册并登录")
    reg = client.post("/api/auth/register", json={
        "username": f"smoke3_{suffix}",
        "email": f"smoke3_{suffix}@example.com",
        "password": "Smoke#12345",
    })
    assert reg.status_code == 200, reg.text
    login = client.post("/api/auth/login",
                        data={"username": f"smoke3_{suffix}", "password": "Smoke#12345"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    ok("logged in")

    # ── A. URL 导入（本地受控网页）────────────────────────────────
    step("A. URL 导入：本地受控网页 → 解析 ready")
    server = ThreadingHTTPServer(("127.0.0.1", ARTICLE_PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        imp = client.post("/api/documents/from-url",
                          json={"url": f"http://127.0.0.1:{ARTICLE_PORT}/article.html"},
                          headers=headers)
        assert imp.status_code == 200, imp.text
        doc = imp.json()
        doc_id = doc["id"]
        doc_ids.append(doc_id)
        status = doc.get("status")
        if status != "ready":  # 异步路径则轮询
            for _ in range(30):
                time.sleep(2)
                d = client.get(f"/api/documents/{doc_id}", headers=headers).json()
                status = d.get("status")
                if status == "ready":
                    break
                assert status != "failed", f"url 导入失败：{d}"
        assert status == "ready", f"最终状态 {status}"
        ok(f"doc {doc_id[:8]}… ready（trafilatura 提取成功）")
    except Exception as e:  # noqa: BLE001
        failures += 1
        print(f"  ✗ URL 导入失败：{e}")
    finally:
        server.shutdown()

    # ── B. TTS ────────────────────────────────────────────────────
    step("B. TTS：voices 列表 + 合成音频流")
    try:
        v = client.get("/api/tts/voices", headers=headers)
        assert v.status_code == 200 and isinstance(v.json(), dict) and v.json(), v.text
        ok(f"voices 分组 {len(v.json())} 组")
        t = client.post("/api/tts/generate",
                        json={"text": "你好，这是冒烟测试。"}, headers=headers)
        assert t.status_code == 200, t.text
        body = t.content
        assert t.headers.get("content-type", "").startswith("audio"), t.headers
        assert len(body) > 1000, f"音频过短：{len(body)}B"
        assert body[:3] == b"ID3" or body[0] == 0xFF, "非 MP3 魔数"
        ok(f"音频流合法（{len(body)}B MP3）")
    except AssertionError:
        failures += 1
        raise
    except Exception as e:  # noqa: BLE001
        skip(f"TTS 依赖微软边缘网络（{type(e).__name__}: {e}）")

    # ── C/D/E. LLM 段 ────────────────────────────────────────────
    # Key 来源优先级：SMOKE_LLM_* 环境变量 → backend/.env 的 OPENAI_*（自动回退，
    # 占位/样例值会被过滤）。Key 仅在进程内使用，绝不打印。
    def _resolve_llm_creds():
        key = os.environ.get("SMOKE_LLM_API_KEY", "").strip()
        base = os.environ.get("SMOKE_LLM_BASE_URL", "").strip()
        model = os.environ.get("SMOKE_LLM_MODEL", "").strip()
        if not key:
            env_file = pathlib.Path(__file__).resolve().parent.parent / "backend" / ".env"
            if env_file.exists():
                vals = {}
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        vals[k.strip()] = v.strip()
                cand = vals.get("OPENAI_API_KEY", "")
                if cand and "replace" not in cand.lower() and cand != "sk-dummy":
                    key = cand
                    base = base or vals.get("OPENAI_BASE_URL", "")
                    model = model or vals.get("OPENAI_MODEL", "")
        return key, base, model

    api_key, env_base, env_model = _resolve_llm_creds()
    step("C/D/E. LLM 全链路（chat ask / 转换×N / 出题判分）")
    if not api_key:
        skip("无可用 Key：设置 SMOKE_LLM_API_KEY 或在 backend/.env 填入 OPENAI_API_KEY 后重跑")
    else:
        base_url = env_base or "https://api.openai.com/v1"
        model = env_model or "gpt-4o-mini"
        cfg = client.post("/api/config/llm", json={
            "provider": "custom", "api_key": api_key, "base_url": base_url,
            "model_name": model, "temperature": 0.7, "max_tokens": 2048,
            "embedding_model": "shibing624/text2vec-base-chinese",
            "embedding_dimension": 768,
        }, headers=headers)
        assert cfg.status_code == 200, cfg.text
        ok(f"config 已注入（model={model}, key 已隐藏）")

        # C. chat ask（RAG 检索需至少一篇 ready 文档：先传极小 txt）
        up_ask = client.post("/api/documents/upload", headers=headers, files={
            "file": (f"ask_{suffix}.txt", "一加一等于二。二加二等于四。".encode(), "text/plain"),
        })
        assert up_ask.status_code == 200, up_ask.text
        ask_doc = up_ask.json()["id"]
        doc_ids.append(ask_doc)
        for _ in range(20):
            d0 = client.get(f"/api/documents/{ask_doc}", headers=headers).json()
            if d0.get("status") == "ready":
                break
            time.sleep(1)
        ask = client.post("/api/chat/ask", json={
            "question": "根据文档回答：一加一等于几？只回答数字。",
            "document_ids": [ask_doc], "stream": False,
        }, headers=headers)
        assert ask.status_code == 200, ask.text
        answer = str(ask.json().get("answer") or ask.json().get("response") or "")
        assert answer.strip(), ask.text
        ok(f"chat 直答返回 {len(answer)} 字：{answer[:40]}…")

        # D. 转换全类型
        types = client.get("/api/transform/transformations", headers=headers).json()
        keys = [t2["key"] if isinstance(t2, dict) else str(t2) for t2 in types]
        ok(f"转换类型 {len(keys)} 个：{keys}")
        src = ("向量数据库用于高维向量的存储与检索。FAISS 支持余弦相似度，"
               "HNSW 图索引兼顾召回与速度。RAG 先语义召回再由 LLM 生成答案。") * 3
        bad = []
        for k in keys:
            tr = client.post("/api/transform", json={
                "transform_type": k, "source_text": src,
                "source_title": "向量检索概述",
            }, headers=headers)
            if tr.status_code != 200:
                bad.append(f"{k}:HTTP{tr.status_code}")
                continue
            res = tr.json().get("result") or tr.json().get("content") or ""
            if not str(res).strip():
                bad.append(f"{k}:空结果")
        assert not bad, f"转换失败项：{bad}"
        ok(f"{len(keys)} 种转换全部产出非空结果")

        # E. 真实出题 + 判分
        up = client.post("/api/documents/upload", headers=headers, files={
            "file": (f"quiz_{suffix}.txt",
                     ("向量数据库以 FAISS 为代表，支持余弦相似度检索。"
                      "HNSW 是近似最近邻图索引。RAG 先召回后生成。" ) * 20,
                     "text/plain")})
        assert up.status_code == 200, up.text
        qdoc = up.json()["id"]
        doc_ids.append(qdoc)
        for _ in range(30):
            time.sleep(2)
            d = client.get(f"/api/documents/{qdoc}", headers=headers).json()
            if d.get("status") == "ready":
                break
            assert d.get("status") != "failed", d
        gq = client.post("/api/quiz/generate", json={
            "document_ids": [qdoc], "choice_count": 1, "short_answer_count": 1,
        }, headers=headers)
        assert gq.status_code == 200, gq.text
        quizzes = gq.json()["quizzes"]
        assert len(quizzes) >= 2, f"出题数量不足：{len(quizzes)}"
        choice = next((q for q in quizzes if q["question_type"] == "choice"), None)
        short = next((q for q in quizzes if q["question_type"] == "short_answer"), None)
        # 服务端不下发答案（防作弊）；用 submit 回传的 correct_answer 做元验证：
        # 探测 → 判对 → 判错，三步覆盖判分正向与负向路径
        letters = sorted({o.strip()[0] for o in (choice.get("options") or []) if o and o.strip()})

        def _submit(letter):
            return client.post("/api/quiz/submit",
                               json={"quiz_id": choice["id"], "user_answer": letter},
                               headers=headers).json()

        probe = _submit(letters[0])
        correct_letter = probe["correct_answer"].strip()[:1]
        hit = _submit(correct_letter)
        assert hit["is_correct"] is True, f"正确答案({correct_letter})被判错：{hit}"
        ok(f"正确答案({correct_letter})判对")
        wrong_letter = next(l for l in letters if l != correct_letter)
        miss = _submit(wrong_letter)
        assert miss["is_correct"] is False, f"错误选项({wrong_letter})被判对：{miss}"
        ok(f"错误选项({wrong_letter})判错；服务端答案={probe['correct_answer']}")
        if short:
            # 语义等价改写（非原文照抄），考察 LLM 裁判而非字符串匹配
            paraphrase = ("向量数据库用来存放高维向量并做相似度检索，"
                          "FAISS 和 HNSW 图索引是这类技术的代表。")
            sj = client.post("/api/quiz/submit",
                             json={"quiz_id": short["id"], "user_answer": paraphrase},
                             headers=headers).json()
            print(f"  ℹ 简答语义裁判结果（不硬断言）：is_correct={sj['is_correct']}, "
                  f"reason={str(sj.get('explanation'))[:60]}")
        hist = client.get("/api/quiz/result-history", headers=headers).json()
        assert isinstance(hist, list) and len(hist) >= 2, hist
        ok(f"答题历史落库 {len(hist)} 条")

    print("\n" + ("✅ ALL PASSED" if failures == 0 else f"❌ {failures} FAILED"))
    return 1 if failures else 0
    # cleanup：文档随用户保留无碍（本地库），如需彻底清理可扩展 DELETE


if __name__ == "__main__":
    sys.exit(main())
