"""BM25 词法基线：rank_bm25 + 混合分词（零外部服务）。"""

from __future__ import annotations

from collections.abc import Mapping

from evaluation.baselines.tokenize import tokenize
from evaluation.datasets.base import EvalDataset


def retrieve_bm25(
    ds: EvalDataset,
    queries: Mapping[str, str],
    top_k: int,
) -> dict[str, list[str]]:
    """对每个 query 返回 top_k 排名的 chunk id 列表。"""
    from rank_bm25 import BM25Okapi

    ids = list(ds.corpus)
    tokenized_corpus = [tokenize(ds.corpus[cid]) for cid in ids]
    bm25 = BM25Okapi(tokenized_corpus)

    run: dict[str, list[str]] = {}
    for qid, q in queries.items():
        scores = bm25.get_scores(tokenize(q))
        order = sorted(range(len(ids)), key=lambda i: -scores[i])[:top_k]
        run[qid] = [ids[i] for i in order]
    return run
