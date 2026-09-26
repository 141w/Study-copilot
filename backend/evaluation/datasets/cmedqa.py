"""CMedQA（中文医疗问答检索）adapter。

数据源 ``mteb/CmedqaRetrieval``（BEIR 格式，结构与 MMarco 相同）：
- config ``queries``：患者提问
- config ``corpus``：医生回答（gold 段落）
- config ``default``：qrels（query-id / corpus-id / score）

约 10 万条回答、60MB 评测子集，全量读入内存后走统一抽样。
注意：另有一个 ``mteb/CMedQAv1-reranking`` 是 reranking 格式
（query + pos + negs），与本检索评测不兼容，请勿混用。
"""

from __future__ import annotations

from evaluation.datasets.base import EvalDataset, sample_dataset

REPO = "mteb/CmedqaRetrieval"


def _load(repo: str, config: str) -> list[dict]:
    from datasets import load_dataset

    return list(load_dataset(repo, config, split="dev"))


def load_cmedqa(
    n_queries: int = 300,
    seed: int = 42,
    distractor_ratio: float = 10.0,
    full_corpus: bool = False,
) -> EvalDataset:
    """加载并抽样 CMedQA。参数含义见 mmarco.load_mmarco。"""
    qrels_raw: dict[str, dict[str, int]] = {}
    for row in _load(REPO, "default"):
        qid, cid = row["query-id"], row["corpus-id"]
        qrels_raw.setdefault(qid, {})[cid] = int(row["score"])

    queries_all = {row["_id"]: row["text"] for row in _load(REPO, "queries")}
    corpus_all = {row["_id"]: row["text"] for row in _load(REPO, "corpus")}

    qrels = {q: rel for q, rel in qrels_raw.items() if q in queries_all}

    ds = EvalDataset(name="cmedqa", corpus=corpus_all, queries=queries_all, qrels=qrels)
    return sample_dataset(ds, n_queries, seed, distractor_ratio, full_corpus=full_corpus)
