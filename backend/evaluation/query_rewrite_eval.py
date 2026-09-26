"""Phase 5：查询改写（query rewrite）的检索影响评测。

对比同一 query 的两种检索路径：
- 直接检索：hybrid（原始 query）
- 生产路径：RAGEngine._rewrite_query 改写后 hybrid（模拟 ask() 的改写步骤）

说明：生产 ask() 对每个 query 先做 LLM 改写（带会话历史）。本评测为
单轮场景（空历史），衡量改写对检索召回的净影响——改写对单轮 query
若是恒等操作，delta 应接近 0（其真实价值在多轮上下文，需多轮数据集
才能评测，见规划文档 Phase 5）。

用法（主 venv，需评测 PG 与 LLM key）：

    python -m evaluation.query_rewrite_eval --dataset mmarco --n-queries 100
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from evaluation.env_util import ensure_eval_env

ensure_eval_env()


async def _run_dataset(name: str, n_queries: int, seed: int, top_k: int) -> dict:
    from evaluation.datasets.registry import load_eval_dataset
    from evaluation.harness import evaluate_retrieval
    from evaluation.self_built import retrieve_hybrid

    ds = load_eval_dataset(name, n_queries, seed, 10.0)
    print(f"[load] {ds.name}: {len(ds.queries)} queries")

    # 1. 直接检索（原始 query）
    run_direct = await retrieve_hybrid(ds, ds.queries, top_k)

    # 2. 生产路径：LLM 改写后检索
    # 循环导入规避：先加载 app.agent 包再导入 RAGEngine（同 self_built.py）
    import app.agent  # noqa: F401
    from app.core.rag_engine import RAGEngine

    engine = RAGEngine()
    rewritten: dict[str, str] = {}
    changed = 0
    for qid, q in ds.queries.items():
        rq = await engine._rewrite_query(q, [], None)
        rewritten[qid] = rq
        if rq != q:
            changed += 1
    run_rewrite = await retrieve_hybrid(ds, rewritten, top_k)

    m_direct = evaluate_retrieval(f"{name}-direct", run_direct, ds.qrels, k_values=(5, 10))
    m_rewrite = evaluate_retrieval(f"{name}-rewrite", run_rewrite, ds.qrels, k_values=(5, 10))

    print(f"[done] {name}: 改写改变了 {changed}/{len(ds.queries)} 条 query")
    print("  direct : " + m_direct.summary_line())
    print("  rewrite: " + m_rewrite.summary_line())
    return {
        "dataset": name,
        "n_queries": m_direct.n_queries,
        "changed_queries": changed,
        "direct": {"recall@5": m_direct.recall[5], "recall@10": m_direct.recall[10]},
        "rewrite": {"recall@5": m_rewrite.recall[5], "recall@10": m_rewrite.recall[10]},
        "delta_recall@10": m_rewrite.recall[10] - m_direct.recall[10],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluation.query_rewrite_eval", description="查询改写检索影响评测"
    )
    parser.add_argument("--dataset", default="mmarco", help="数据集（默认 mmarco）")
    parser.add_argument("--n-queries", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--out", default="/tmp/rewrite_eval.json")
    args = parser.parse_args(argv)

    result = asyncio.run(_run_dataset(args.dataset, args.n_queries, args.seed, args.top_k))
    Path(args.out).write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[rewrite-eval] 结果 -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
