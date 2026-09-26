"""Phase 5：Agentic 特性量化（自适应策略 + 纠错检索）。

对每个 query 复现生产 ask() 的检索决策链，与「纯 hybrid 检索」对比：

1. 策略选择：AdaptiveRetriever.select_strategy(query, llm)（1 次 LLM 调用）
2. 自适应检索：retrieve_adaptive（SINGLE=top1 / STANDARD=top5 / MULTI_HOP / COMPARE）
3. 质量评分：RetrievalGrader.grade(query, results)（1 次 LLM 调用）
   - 好 -> 采用自适应结果
   - 差 -> 改写重试一次 -> 好则采用，仍差 -> **空结果**（召回归零）
4. 对比：纯 hybrid search(top_k=100) 在同 k 下的 recall

输出：策略分布、grader 触发率、空结果率、自适应 vs 纯 hybrid 的
recall@1/@5 对比、每 query 平均 LLM 调用数。

用法（主 venv，需评测 PG 与 LLM key）：

    python -m evaluation.agentic_features_eval --dataset mmarco --n-queries 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from evaluation.env_util import ensure_eval_env

ensure_eval_env()


def _eval_ids(results: list[dict]) -> list[str]:
    return [r["chunk"].get("metadata", {}).get("eval_id", "") for r in results]


def _recall_at(run_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for cid in run_ids[:k] if cid in relevant)
    return hits / len(relevant)


async def _run_dataset(name: str, n_queries: int, seed: int) -> dict:
    import app.agent  # noqa: F401 - 循环导入规避（同 self_built.py）
    from app.core.adaptive_retriever import AdaptiveRetriever
    from app.core.llm import LLM
    from app.core.rag_engine import RAGEngine
    from app.core.retrieval_grader import retrieval_grader
    from evaluation.datasets.registry import load_eval_dataset
    from evaluation.self_built import retrieve_hybrid

    ds = load_eval_dataset(name, n_queries, seed, 10.0)
    print(f"[load] {ds.name}: {len(ds.queries)} queries")

    llm = LLM.from_config(None)
    engine = RAGEngine()
    adaptive = AdaptiveRetriever()
    doc_id = f"eval-{ds.name}"

    # 纯 hybrid 基线（top-100 全序列表，用于 recall@1/@5 同 k 对比）
    plain = await retrieve_hybrid(ds, ds.queries, 100)

    strategies = Counter()
    trigger_count = 0
    empty_count = 0
    llm_calls = 0
    plain_r1 = plain_r5 = 0.0
    adaptive_r1 = adaptive_r5 = 0.0
    n = 0

    for qid, query in ds.queries.items():
        relevant = {c for c, rel in ds.qrels.get(qid, {}).items() if rel > 0}
        if not relevant:
            continue
        n += 1

        # 纯 hybrid 基线
        plain_ids = plain.get(qid, [])
        plain_r1 += _recall_at(plain_ids, relevant, 1)
        plain_r5 += _recall_at(plain_ids, relevant, 5)

        # 1. 策略选择（1 次 LLM）
        strategy = await adaptive.select_strategy(query, llm)
        strategies[strategy.value] += 1
        llm_calls += 1

        # 2. 自适应检索
        results, _ = await adaptive.retrieve_adaptive([doc_id], query, strategy, engine, None)
        llm_calls += 0  # retrieve_adaptive 的 MULTI_HOP/COMPARE 内部另有 LLM 调用（未计）

        # 3. 质量评分（1 次 LLM）
        quality = await retrieval_grader.grade(query, results, None)
        llm_calls += 1

        final_ids: list[str] = _eval_ids(results)
        if not quality.is_good:
            trigger_count += 1
            # 4. 纠错：改写重试（改写 1 次 + 重试评分 1 次 LLM）
            rewritten = await engine._rewrite_query(query, [], None)
            llm_calls += 1
            retry_results, _ = await engine.retrieve([doc_id], rewritten, 5)
            quality_retry = await retrieval_grader.grade(query, retry_results, None)
            llm_calls += 1
            if quality_retry.is_good:
                final_ids = _eval_ids(retry_results)
            else:
                final_ids = []  # 生产行为：两次都差 -> 空结果
                empty_count += 1

        adaptive_r1 += _recall_at(final_ids, relevant, 1)
        adaptive_r5 += _recall_at(final_ids, relevant, 5)

        if n % 20 == 0:
            print(f"  [{name}] {n}/{len(ds.queries)} processed")

    summary = {
        "dataset": name,
        "n_queries": n,
        "strategy_distribution": dict(strategies),
        "grader_trigger_rate": round(trigger_count / n, 4) if n else 0,
        "empty_result_rate": round(empty_count / n, 4) if n else 0,
        "avg_llm_calls_per_query": round(llm_calls / n, 2) if n else 0,
        "plain_hybrid": {"recall@1": round(plain_r1 / n, 4), "recall@5": round(plain_r5 / n, 4)},
        "agentic_path": {"recall@1": round(adaptive_r1 / n, 4), "recall@5": round(adaptive_r5 / n, 4)},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluation.agentic_features_eval", description="Agentic 特性量化评测"
    )
    parser.add_argument("--dataset", default="mmarco")
    parser.add_argument("--n-queries", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="/tmp/agentic_eval.json")
    args = parser.parse_args(argv)

    result = asyncio.run(_run_dataset(args.dataset, args.n_queries, args.seed))
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[agentic-eval] 结果 -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
