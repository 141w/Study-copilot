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

import io
import os
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
    api_key = os.environ.get("SMOKE_LLM_API_KEY", "").strip()
    step("C/D/E. LLM 全链路（chat ask / 转换×N / 出题判分）")
    if not api_key:
        skip("未设置 SMOKE_LLM_API_KEY——配置后重跑本脚本即自动执行该段")
    else:
        base_url = os.environ.get("SMOKE_LLM_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("SMOKE_LLM_MODEL", "gpt-4o-mini")
        cfg = client.post("/api/config/llm", json={
            "provider": "custom", "api_key": api_key, "base_url": base_url,
            "model_name": model, "temperature": 0.7, "max_tokens": 2048,
            "embedding_model": "shibing624/text2vec-base-chinese",
            "embedding_dimension": 768,
        }, headers=headers)
        assert cfg.status_code == 200, cfg.text
        ok(f"config 已注入（model={model}, key 已隐藏）")

        # C. chat ask 直答
        ask = client.post("/api/chat/ask", json={
            "question": "只回答一个数字：1+1=?", "document_ids": [], "stream": False,
        }, headers=headers)
        assert ask.status_code == 200, ask.text
        answer = str(ask.json().get("answer") or ask.json().get("response") or "")
        assert answer.strip(), ask.text
        assert "2" in answer, f"直答异常：{answer[:80]}"
        ok(f"chat 直答包含 2：{answer[:40]}…")

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
        assert choice and choice.get("answer"), f"选择题缺失：{choice}"
        self_ans = client.post("/api/quiz/submit",
                               json={"quiz_id": choice["id"], "user_answer": choice["answer"]},
                               headers=headers).json()
        assert self_ans["is_correct"] is True, f"自答判错：{self_ans}"
        ok(f"选择自答({choice['answer']})判对")
        opts = choice.get("options") or []
        wrong = next((o[0] for o in opts if o and o[0] != choice["answer"][:1]), "Z")
        wrong_ans = client.post("/api/quiz/submit",
                                json={"quiz_id": choice["id"], "user_answer": wrong},
                                headers=headers).json()
        assert wrong_ans["is_correct"] is False, f"错误选项被判对：{wrong_ans}"
        ok(f"错误选项({wrong})判错")
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
