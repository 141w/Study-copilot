"""C-MSMARCO（中文 MS MARCO 段落检索）adapter。

数据源 ``mteb/MMarcoRetrieval``（BEIR 格式）：
- config ``queries``（split dev）：``_id`` / ``text``
- config ``corpus``（split dev）：``_id`` / ``text``（评测子集，约 20MB）
- config ``default``（split dev）：``query-id`` / ``corpus-id`` / ``score``（qrels）

适配流程：全量读入三元组（评测子集规模可控）→ 复用
:func:`evaluation.datasets.base.sample_dataset` 做固定 seed 抽样与
distractor 混入。抽样参数记入数据集 name，保证分数可追溯。
"""

from __future__ import annotations

from evaluation.datasets.base import EvalDataset, sample_dataset

REPO = "mteb/MMarcoRetrieval"


def _load(repo: str, config: str) -> list[dict]:
    from datasets import load_dataset

    return list(load_dataset(repo, config, split="dev"))


def load_mmarco(
    n_queries: int = 300,
    seed: int = 42,
    distractor_ratio: float = 10.0,
    full_corpus: bool = False,
) -> EvalDataset:
    """加载并抽样 C-MSMARCO。

    Args:
        n_queries: 抽中的 query 数。
        seed: 随机种子（固定可复现）。
        distractor_ratio: 混入无关 chunk 与相关 chunk 总数之比。
        full_corpus: True 时候选池保留全库（对齐 MTEB/BEIR 口径）。
    """
    qrels_raw: dict[str, dict[str, int]] = {}
    for row in _load(REPO, "default"):
        qid, cid = row["query-id"], row["corpus-id"]
        qrels_raw.setdefault(qid, {})[cid] = int(row["score"])

    queries_all = {row["_id"]: row["text"] for row in _load(REPO, "queries")}
    corpus_all = {row["_id"]: row["text"] for row in _load(REPO, "corpus")}

    # 防御：qrels 引用的 query 不在 queries 配置中时剔除，避免 __post_init__ 校验失败
    qrels = {q: rel for q, rel in qrels_raw.items() if q in queries_all}

    ds = EvalDataset(name="mmarco", corpus=corpus_all, queries=queries_all, qrels=qrels)
    return sample_dataset(ds, n_queries, seed, distractor_ratio, full_corpus=full_corpus)
