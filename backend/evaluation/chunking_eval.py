"""Phase 5：chunking 策略对比（真实文档，fixed / semantic / hierarchical）。

素材（真实文档）：
- rag-stress-corpus.pdf（100 页技术手册，取前 N 页）
- docs/**/*.md（项目文档，取 1-2 篇）

流程（每文档）：
1. 三种 chunker 分块（app.core.chunker，与生产同一件事）
2. 采样段落 -> LLM 生成问题（gold = 原段落；相关性规则 =
   chunk 含段落归一化前 80 字符）
3. 每种变体入库（PG doc_id 隔离，add_chunks 与生产一致）
4. hybrid 检索，计算 recall@1/5/10
5. 输出三策略对比 + chunk 统计（数量/均长）

用法（主 venv，需评测 PG 与 LLM key）：

    python -m evaluation.chunking_eval --pdf-pages 40 --questions 12
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import Path

from evaluation.env_util import ensure_eval_env

ensure_eval_env()

REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_LEN = 80  # gold 段落归一化前缀长度（相关性探针）


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "")).lower()


def _pdf_pages(path: Path, max_pages: int) -> list[dict]:
    import pymupdf

    doc = pymupdf.open(path)
    pages = []
    for i in range(min(max_pages, doc.page_count)):
        text = doc[i].get_text()
        if text.strip():
            pages.append({"text": text, "page": i + 1})
    return pages


def _md_pages(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return [{"text": text, "page": 1}]


def _sample_gold(doc_text: str, n: int, seed: int) -> list[str]:
    """按换行切段（PDF 文本通常无空行），取 120-500 字符的段落采样。

    固定 seed 可复现；候选不足时放宽到 80-800 字符。
    """
    import random

    paras = [p.strip() for p in re.split(r"\n+", doc_text)]
    paras = [p for p in paras if 120 <= len(p) <= 500]
    if len(paras) < n:
        paras = [p.strip() for p in re.split(r"\n+", doc_text)]
        paras = [p for p in paras if 80 <= len(p) <= 800]
    rng = random.Random(seed)
    return rng.sample(paras, min(n, len(paras)))


async def _gen_question(paragraph: str, idx: int) -> str:
    """LLM 基于段落生成问题；超时/失败回退到模板问题（评测不依赖 LLM 可用性）。"""
    from openai import AsyncOpenAI

    from app.config import settings

    try:
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=60.0,
        )
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "基于以下技术文档段落，生成一个具体的阅读理解问题"
                        "（答案必须能在该段落中找到）。只输出问题本身，不要输出答案。\n\n"
                        f"段落：\n{paragraph}"
                    ),
                }
            ],
            temperature=0.3,
            max_tokens=128,
        )
        q = (resp.choices[0].message.content or "").strip()
        if q:
            return q
    except Exception as exc:  # noqa: BLE001 - 回退模板问题，保证评测可完成
        print(f"  [warn] LLM 出题失败（段落{idx}），回退模板问题: {exc}")

    first = re.split(r"[。！？.!?]", paragraph)[0][:40]
    return f"关于「{first}」这一内容，文档中是怎么阐述的？"


def _relevant_ids(chunks: list[dict], gold: str) -> set[str]:
    """相关性规则：chunk 文本包含 gold 归一化前 80 字符。"""
    probe = _norm(gold)[:_PROBE_LEN]
    if len(probe) < 20:  # 探针太短则规则不可靠，跳过该 gold
        return set()
    return {c["id"] for c in chunks if probe in _norm(c.get("text", ""))}


async def _eval_doc(
    doc_name: str,
    pages: list[dict],
    n_questions: int,
    seed: int,
) -> dict:
    import app.agent  # noqa: F401 - 循环导入规避
    from app.core.chunker import FixedChunker, HierarchicalChunker, SemanticChunker
    from app.core.llm import LLM  # noqa: F401 - 确认 llm 依赖可导入
    from app.core.pgvector_store import PgVectorStore
    from app.core.rag_engine import RAGEngine  # noqa: F401
    from evaluation.harness import evaluate_retrieval
    from evaluation.self_built import _ensure_schema, ensure_document_row

    await _ensure_schema()

    doc_text = (chr(10) + chr(10)).join(p["text"] for p in pages)
    golds = _sample_gold(doc_text, n_questions, seed)
    print(f"[doc] {doc_name}: pages={len(pages)} chars={len(doc_text)} gold={len(golds)}")

    # 问题生成（LLM）
    questions: dict[str, str] = {}
    for i, gold in enumerate(golds):
        q = await _gen_question(gold, i)
        questions[f"q{i}"] = q
        if (i + 1) % 5 == 0:
            print(f"  [{doc_name}] questions {i + 1}/{len(golds)}")

    # 三种分块变体
    variants = {
        "fixed": FixedChunker,
        "semantic": SemanticChunker,
        "hierarchical": HierarchicalChunker,
    }
    results = {}
    for vname, cls in variants.items():
        chunker = cls()
        chunks = await chunker.chunk_document(pages, f"{doc_name}")
        # qrels：gold -> 包含它的 chunk id
        qrels: dict[str, dict[str, int]] = {}
        for i, gold in enumerate(golds):
            rel = _relevant_ids(chunks, gold)
            if rel:
                qrels[f"q{i}"] = {cid: 1 for cid in rel}
        if not qrels:
            print(f"  [{doc_name}/{vname}] 无有效 gold 映射，跳过")
            continue

        # 入库（doc_id 隔离；eval_id 回传；is_parent 元数据随 chunk 保留）
        doc_id = f"eval-chunk-{doc_name}-{vname}"
        await ensure_document_row(doc_id, f"chunk-eval-{doc_name}-{vname}")
        store = PgVectorStore(user_id="eval")
        ingest = [
            {**{k: v for k, v in c.items() if k != "id"}, "text": c["text"], "eval_id": c["id"]}
            for c in chunks
        ]
        await store.add_chunks(ingest, doc_id, db=None)

        # hybrid 检索
        run: dict[str, list[str]] = {}
        for qid, q in questions.items():
            if qid not in qrels:
                continue
            res = await store.search(q, [doc_id], top_k=100)
            run[qid] = [r["chunk"].get("metadata", {}).get("eval_id", "") for r in res]

        m = evaluate_retrieval(f"{doc_name}-{vname}", run, qrels, k_values=(1, 5, 10))
        sizes = [c.get("char_count", 0) for c in chunks]
        results[vname] = {
            "n_chunks": len(chunks),
            "avg_chars": round(sum(sizes) / len(sizes), 1) if sizes else 0,
            "recall@1": round(m.recall[1], 4),
            "recall@5": round(m.recall[5], 4),
            "recall@10": round(m.recall[10], 4),
            "n_queries": m.n_queries,
        }
        print(f"  [{doc_name}/{vname}] chunks={len(chunks)} avg={results[vname]['avg_chars']} " + m.summary_line())
    return {"doc": doc_name, "variants": results}


async def _main(pdf_pages: int, n_questions: int, seed: int, out: str) -> int:
    docs: list[tuple[str, list[dict]]] = []

    pdf = REPO_ROOT / "rag-stress-corpus.pdf"
    if pdf.exists():
        docs.append(("stress-pdf", _pdf_pages(pdf, pdf_pages)))

    md_candidates = [
        REPO_ROOT / "docs/4-DEVELOPMENT/testing.md",
        REPO_ROOT / "docs/2-ARCHITECTURE/index.md",
    ]
    for md in md_candidates:
        if md.exists():
            docs.append((md.stem, _md_pages(md)))

    if not docs:
        print("未找到可用文档（rag-stress-corpus.pdf / docs/*.md）")
        return 2

    all_results = []
    for name, pages in docs:
        all_results.append(await _eval_doc(name, pages, n_questions, seed))

    Path(out).write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[chunking-eval] 结果 -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluation.chunking_eval", description="chunking 策略对比评测（真实文档）"
    )
    parser.add_argument("--pdf-pages", type=int, default=40, help="PDF 取材页数")
    parser.add_argument("--questions", type=int, default=12, help="每文档问题数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="/tmp/chunking_eval.json")
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.pdf_pages, args.questions, args.seed, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
