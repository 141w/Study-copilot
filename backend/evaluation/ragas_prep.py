"""P6 数据准备：hybrid 生产路径检索 + LLM 生成答案，产出 RAGAS 评测数据 JSON。

用法（主 venv，需 PG+pgvector 与 LLM key）：

    python -m evaluation.ragas_prep --datasets mmarco,cmedqa --n-queries 30 --out /tmp/ragas_data.json

产出 JSON 列表：[{question, contexts, answer, ground_truth, dataset}, ...]
- contexts:     hybrid（生产 pgvector SQL 路径）检索的 top-k 段落
- answer:       LLM（.env 配置，与线上生成同模型）基于 contexts 生成的答案
- ground_truth: qrels 标注的 gold 段落文本（context_recall 的参照）
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from evaluation.env_util import ensure_eval_env

# 必须在 import app.* 之前
ensure_eval_env()

_ANSWER_SYSTEM = (
    "你是学习助手。严格基于给定资料回答问题：资料中没有的信息不要编造，回答用中文、简洁直接。"
)


def _build_user_prompt(question: str, contexts: list[str]) -> str:
    ctx = chr(10).join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))
    nl = chr(10)
    return f"资料：{nl}{ctx}{nl}{nl}问题：{question}"


async def _generate_answer(question: str, contexts: list[str]) -> str:
    """调用 .env 配置的 LLM 生成答案（与线上 chat 生成同模型配置）。"""
    from openai import AsyncOpenAI

    from app.config import settings

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _ANSWER_SYSTEM},
            {"role": "user", "content": _build_user_prompt(question, contexts)},
        ],
        temperature=0.3,
        max_tokens=512,
    )
    return (resp.choices[0].message.content or "").strip()


async def _prepare_dataset(
    name: str, n_queries: int, seed: int, top_k: int, retrieval: str = "hybrid", noise: bool = False
) -> list[dict]:
    import random

    from evaluation.datasets.registry import load_eval_dataset

    ds = load_eval_dataset(name, n_queries, seed, 10.0)

    run: dict[str, list[str]] = {}
    if not noise:
        if retrieval == "dense":
            # 内存 dense 通道：无 PG 依赖，绕开本机 FTS 降级底座做噪声实验
            from evaluation.baselines.dense import retrieve_dense

            run = await retrieve_dense(ds, ds.queries, top_k)
        else:
            from evaluation.self_built import retrieve_hybrid

            run = await retrieve_hybrid(ds, ds.queries, top_k)
        print(f"[prep] {ds.name}: {len(ds.queries)} queries, {retrieval} 检索 top-{top_k}")
    else:
        print(
            f"[prep] {ds.name}: {len(ds.queries)} queries, 噪声注入构造（1 gold + {top_k - 1} 随机非 gold）"
        )

    rng = random.Random(seed)
    records: list[dict] = []
    for i, (qid, question) in enumerate(ds.queries.items()):
        gold_ids = [cid for cid, rel in ds.qrels.get(qid, {}).items() if rel > 0]
        if noise:
            # 噪声实验不依赖检索：gold 来自 qrels，噪声块从 corpus 随机抽（确定性 seed）
            if not gold_ids:
                continue
            pool = [cid for cid in ds.corpus if cid not in set(gold_ids)]
            picks = [gold_ids[0]] + rng.sample(pool, min(top_k - 1, len(pool)))
        else:
            picks = [c for c in run.get(qid, []) if c][:top_k]
        contexts = [ds.corpus[cid] for cid in picks if cid in ds.corpus]
        gold = " ".join(ds.corpus[cid] for cid in gold_ids if cid in ds.corpus)
        if not contexts:
            continue
        answer = await _generate_answer(question, contexts)
        records.append(
            {
                "question": question,
                "contexts": contexts,
                "answer": answer,
                "ground_truth": gold,
                "dataset": name,
                "noised": noise,
            }
        )
        if (i + 1) % 10 == 0:
            print(f"  [{name}] {i + 1}/{len(ds.queries)} done")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evaluation.ragas_prep", description="生成 RAGAS 评测数据（检索通道可选 + LLM 生成）"
    )
    parser.add_argument("--datasets", default="mmarco,cmedqa", help="逗号分隔数据集")
    parser.add_argument("--n-queries", type=int, default=30, help="每数据集 query 数")
    parser.add_argument("--top-k", type=int, default=5, help="检索上下文条数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--retrieval",
        choices=("hybrid", "dense"),
        default="hybrid",
        help="context 来源通道：hybrid=生产 pgvector（需 PG）；dense=内存向量（零服务）",
    )
    parser.add_argument(
        "--noise",
        action="store_true",
        help="噪声注入模式：1 gold + top_k-1 随机非 gold 构造 contexts（配 ragas_eval noise 指标）",
    )
    parser.add_argument("--out", default="evaluation/data/ragas_data.json")
    args = parser.parse_args(argv)

    names = [d.strip() for d in args.datasets.split(",") if d.strip()]

    async def _run() -> list[dict]:
        records: list[dict] = []
        for name in names:
            records.extend(
                await _prepare_dataset(
                    name, args.n_queries, args.seed, args.top_k, args.retrieval, args.noise
                )
            )
        return records

    records = asyncio.run(_run())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[prep] 已写出 {len(records)} 条 -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
