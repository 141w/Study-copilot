"""评测 CLI 入口（完整链路）。

P1-P5 落地后的用法：

    # 冒烟自检（合成数据，无需数据集/网络/PG）
    python -m evaluation.run --self-test

    # 全量：3 数据集 × 4 方法
    python -m evaluation.run --dataset all --methods bm25,dense,hybrid,hybrid-rerank

    # 单数据集 / 调参
    python -m evaluation.run --dataset cmedqa --methods bm25,dense --n-queries 200

    # 全库口径（对齐 MTEB/BEIR，绝对分可向榜单锚定）
    python -m evaluation.run --dataset cmedqa,mmarco --methods bm25 --corpus full

    # 带环境标识（CI zhparser 实例复测打 -zh 标，文件名与 meta.tag 双记录）
    python -m evaluation.run --methods hybrid --name-suffix zh

环境变量：
- EVAL_DATABASE_URL: hybrid 系方法所需 PG+pgvector 实例（优先于 DATABASE_URL）
- DATABASE_URL:      同上（兼容旧用法；默认本文件内置的评测库）
- HF_HUB_CACHE:      模型/数据集缓存目录（默认用户缓存）
- HF_DATASETS_CACHE: 数据集缓存目录（默认 evaluation/data/hf-datasets）
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from evaluation.env_util import ensure_eval_env

# 必须在 import app.* 之前
ensure_eval_env()

from evaluation.datasets.base import EvalDataset  # noqa: E402
from evaluation.datasets.registry import DATASET_NAMES  # noqa: E402
from evaluation.harness import K_VALUES, Metrics, evaluate_retrieval  # noqa: E402
from evaluation.report import write_report  # noqa: E402

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"

# 检索方法分派表：统一 async 签名 (ds, queries, top_k) -> {qid: [chunk_id 降序]}。
# 重依赖在各分支内延迟 import，保持 --help/self-test 零依赖秒起。
RunFn = Callable[[EvalDataset, dict[str, str], int], Awaitable[dict[str, list[str]]]]


async def _bm25(ds: EvalDataset, queries: dict[str, str], top_k: int) -> dict[str, list[str]]:
    from evaluation.baselines.bm25 import retrieve_bm25

    return retrieve_bm25(ds, queries, top_k)


async def _dense(ds: EvalDataset, queries: dict[str, str], top_k: int) -> dict[str, list[str]]:
    from evaluation.baselines.dense import retrieve_dense

    return await retrieve_dense(ds, queries, top_k)


async def _dense_bge(ds: EvalDataset, queries: dict[str, str], top_k: int) -> dict[str, list[str]]:
    from evaluation.baselines.dense import BGE_QUERY_INSTRUCTION, BGE_ZH_SMALL, retrieve_dense_model

    return await retrieve_dense_model(
        ds, queries, top_k, BGE_ZH_SMALL, query_instruction=BGE_QUERY_INSTRUCTION
    )


async def _dense_bge_base(
    ds: EvalDataset, queries: dict[str, str], top_k: int
) -> dict[str, list[str]]:
    from evaluation.baselines.dense import BGE_QUERY_INSTRUCTION, BGE_ZH_BASE, retrieve_dense_model

    return await retrieve_dense_model(
        ds, queries, top_k, BGE_ZH_BASE, query_instruction=BGE_QUERY_INSTRUCTION
    )


async def _dense_qwen3(
    ds: EvalDataset, queries: dict[str, str], top_k: int
) -> dict[str, list[str]]:
    from evaluation.baselines.dense import (
        QWEN3_EMBEDDING,
        QWEN3_INSTRUCTION_TMPL,
        retrieve_dense_model,
    )

    return await retrieve_dense_model(
        ds, queries, top_k, QWEN3_EMBEDDING, query_format=QWEN3_INSTRUCTION_TMPL
    )


async def _dense_bge_m3(
    ds: EvalDataset, queries: dict[str, str], top_k: int
) -> dict[str, list[str]]:
    from evaluation.baselines.dense import BGE_M3, retrieve_dense_model

    return await retrieve_dense_model(ds, queries, top_k, BGE_M3)


async def _hybrid(ds: EvalDataset, queries: dict[str, str], top_k: int) -> dict[str, list[str]]:
    from evaluation.self_built import retrieve_hybrid

    return await retrieve_hybrid(ds, queries, top_k)


async def _hybrid_rerank(
    ds: EvalDataset, queries: dict[str, str], top_k: int
) -> dict[str, list[str]]:
    from evaluation.self_built import retrieve_hybrid_rerank

    return await retrieve_hybrid_rerank(ds, queries, top_k)


RETRIEVERS: dict[str, RunFn] = {
    "bm25": _bm25,
    "dense": _dense,
    "dense-bge": _dense_bge,
    "dense-bge-base": _dense_bge_base,
    "dense-qwen3": _dense_qwen3,
    "dense-bge-m3": _dense_bge_m3,
    "hybrid": _hybrid,
    "hybrid-rerank": _hybrid_rerank,
}

KNOWN_METHODS = tuple(RETRIEVERS)


def _self_test() -> int:
    """合成数据冒烟：验证 harness 指标计算正确（无需数据集/网络）。"""
    import math

    from evaluation.datasets.base import EvalDataset, sample_dataset

    ds = EvalDataset(
        name="synthetic",
        corpus={"c1": "alpha", "c2": "beta", "c3": "gamma"},
        queries={"q1": "a", "q2": "b"},
        qrels={"q1": {"c1": 1}, "q2": {"c2": 1}},
    )
    run = {"q1": ["c1", "c2", "c3"], "q2": ["c3", "c2"]}
    metrics = evaluate_retrieval("synthetic", run, ds.qrels, k_values=(1, 5, 10))

    expected_ndcg10 = (1.0 + 1.0 / math.log2(3)) / 2  # q1 满分 + q2 相关项排第 2 位
    # cp@10：q1 首位命中 AP=1.0；q2 第 2 位命中 AP=P@2=0.5 → 均值 0.75
    expected_cp10 = (1.0 + 0.5) / 2
    ok = (
        metrics.n_queries == 2
        and abs(metrics.recall[10] - 1.0) < 1e-9
        and abs(metrics.hit_rate[1] - 0.5) < 1e-9
        and abs(metrics.mrr[10] - 0.75) < 1e-9
        and abs(metrics.ndcg[10] - expected_ndcg10) < 1e-9
        and abs(metrics.ctx_precision[10] - expected_cp10) < 1e-9
    )

    # 全库口径：corpus 全保留、仅抽 query、name 带 fullcorpus 标识
    big = EvalDataset(
        name="big",
        corpus={f"c{i}": f"text{i}" for i in range(20)},
        queries={f"q{i}": f"query{i}" for i in range(10)},
        qrels={f"q{i}": {f"c{i}": 1} for i in range(10)},
    )
    fc = sample_dataset(big, n_queries=5, seed=1, full_corpus=True)
    ok = (
        ok
        and len(fc.corpus) == 20
        and len(fc.queries) == 5
        and len(fc.qrels) == 5
        and "fullcorpus" in fc.name
    )

    print(metrics.summary_line())
    print("self-test:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def _parse_methods(raw: str) -> list[str]:
    methods = [m.strip() for m in raw.split(",") if m.strip()]
    unknown = [m for m in methods if m not in KNOWN_METHODS]
    if unknown:
        raise SystemExit(f"unknown methods: {unknown}; known: {list(KNOWN_METHODS)}")
    return methods


def _metrics_name(dataset: str, method: str, corpus_mode: str, suffix: str) -> str:
    """指标/文件名键：旧口径（sampled 无 tag）与历史键完全一致，新口径显式加后缀。"""
    name = f"{dataset}-{method}"
    if corpus_mode == "full":
        name += "-full"
    if suffix:
        name += f"-{suffix}"
    return name


async def _run_dataset(
    name: str,
    methods: list[str],
    n_queries: int,
    seed: int,
    distractor_ratio: float,
    top_k: int,
    corpus_mode: str = "sampled",
    name_suffix: str = "",
) -> tuple[list[Metrics], EvalDataset]:
    """加载数据集并逐方法跑检索 + 指标，返回 (Metrics 列表, EvalDataset)。"""
    from evaluation.datasets.registry import load_eval_dataset

    ds = load_eval_dataset(
        name, n_queries, seed, distractor_ratio, full_corpus=(corpus_mode == "full")
    )
    print(
        f"\n[load] {ds.name}: queries={len(ds.queries)} corpus={len(ds.corpus)} "
        f"(n={n_queries}, seed={seed}, dr={distractor_ratio}, corpus={corpus_mode})"
    )

    results: list[Metrics] = []
    for method in methods:
        t0 = time.time()
        try:
            run = await RETRIEVERS[method](ds, ds.queries, top_k)
        except Exception as exc:  # noqa: BLE001 - 单方法失败不拖垮整轮，继续其他方法
            print(f"[fail] {name}-{method} ({time.time() - t0:.1f}s): {exc}")
            continue

        metrics = evaluate_retrieval(
            _metrics_name(name, method, corpus_mode, name_suffix), run, ds.qrels, k_values=K_VALUES
        )
        results.append(metrics)
        print(f"[done] {metrics.name} ({time.time() - t0:.1f}s)")
        print("       " + metrics.summary_line())
    return results, ds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluation.run",
        description="RAG 检索召回率评测（完整链路：数据集 → 基线/自研方法 → 指标 → 报表）",
    )
    parser.add_argument("--self-test", action="store_true", help="合成数据冒烟自检")
    parser.add_argument(
        "--dataset",
        default="all",
        help="数据集：all 或逗号分隔（如 mmarco,cmedqa）",
    )
    parser.add_argument(
        "--methods",
        default="bm25,dense,hybrid,hybrid-rerank",
        help="逗号分隔的方法列表（默认全部四种）",
    )
    parser.add_argument("--n-queries", type=int, default=300, help="抽样 query 数（默认 300）")
    parser.add_argument("--top-k", type=int, default=100, help="检索返回条数（默认 100）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    parser.add_argument("--distractor-ratio", type=float, default=10.0, help="干扰项比例")
    parser.add_argument(
        "--corpus",
        choices=("sampled", "full"),
        default="sampled",
        help="候选池口径：sampled=相关块+distractor（历史口径）；"
        "full=保留完整 corpus 对齐 MTEB/BEIR 全库排名（默认 sampled）",
    )
    parser.add_argument(
        "--name-suffix",
        default="",
        help="指标名/文件名附加标识（如 CI zhparser 实例传 zh），并写入 meta.tag",
    )
    parser.add_argument("--out", default=None, help="报表目录（默认 evaluation/results/）")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    methods = _parse_methods(args.methods)
    if args.dataset.strip() == "all":
        datasets = list(DATASET_NAMES)
    else:
        datasets = [d.strip() for d in args.dataset.split(",") if d.strip()]
        unknown = [d for d in datasets if d not in DATASET_NAMES]
        if unknown:
            raise SystemExit(f"unknown datasets: {unknown}; known: {list(DATASET_NAMES)}")
    out_dir = args.out or str(DEFAULT_RESULTS_DIR)

    async def _run_all() -> Path:
        from app.config import settings

        # 全部数据集共用同一事件循环：app 引擎的 asyncpg 连接池绑定首个
        # 使用它的循环，asyncio.run 每数据集换循环会触发
        # "Future attached to a different loop"。
        all_results: list[Metrics] = []
        for ds_name in datasets:
            try:
                results, _ = await _run_dataset(
                    ds_name,
                    methods,
                    args.n_queries,
                    args.seed,
                    args.distractor_ratio,
                    args.top_k,
                    corpus_mode=args.corpus,
                    name_suffix=args.name_suffix,
                )
            except Exception as exc:  # noqa: BLE001 - 数据集加载失败（gated/网络）跳过不拖垮整轮
                print(f"[skip] dataset {ds_name}: {exc}")
                continue
            all_results.extend(results)

        meta = {
            "datasets": datasets,
            "methods": methods,
            "n_queries": args.n_queries,
            "seed": args.seed,
            "distractor_ratio": args.distractor_ratio,
            "top_k": args.top_k,
            "k_values": list(K_VALUES),
            "corpus": args.corpus,
            "tag": args.name_suffix,
            "embedding_model": getattr(settings, "embedding_model", "?"),
            "pgvector_url": os.environ["DATABASE_URL"].split("@")[-1],
        }
        summary_path, _ = write_report(all_results, meta, out_dir)
        return summary_path

    summary_path = asyncio.run(_run_all())
    print(f"\n报表已生成: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
