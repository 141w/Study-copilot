"""数据集适配层统一抽象。

所有公开数据集（C-MSMARCO / CMedQA / FinanceQA）经各自 adapter 归一化为
EvalDataset，供 harness（指标计算）与 baselines（检索方法）消费。

设计约束（与 app/ 隔离）：
- 本模块不进 app/，不注册路由；
- 不进 pytest 收集（testpaths=["tests"]）；
- 不进覆盖率统计（--cov=app）；
- 重依赖（datasets/mteb/beir）仅在 adapter 内按需 import。
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class EvalDataset:
    """统一评测三元组。

    Attributes:
        name: 数据集名称（用于报表分组）。
        corpus: chunk_id -> 文本，检索候选池。
        queries: query_id -> 查询文本。
        qrels: query_id -> {chunk_id: relevance}。relevance > 0 视为相关；
            保留整数分级以支持未来细粒度标注，二值场景取 1。

    Raises:
        ValueError: qrels 引用了不存在的 query 或 chunk。
    """

    name: str
    corpus: dict[str, str]
    queries: dict[str, str]
    qrels: dict[str, dict[str, int]]

    def __post_init__(self) -> None:
        missing_queries = set(self.qrels) - set(self.queries)
        if missing_queries:
            raise ValueError(f"qrels references unknown queries: {sorted(missing_queries)[:5]}")
        referenced = {cid for rel in self.qrels.values() for cid in rel}
        missing_chunks = referenced - set(self.corpus)
        if missing_chunks:
            raise ValueError(f"qrels references unknown chunks: {sorted(missing_chunks)[:5]}")


def sample_dataset(
    ds: EvalDataset,
    n_queries: int,
    seed: int = 42,
    distractor_ratio: float = 0.0,
    full_corpus: bool = False,
) -> EvalDataset:
    """按固定 seed 抽样 query，返回缩小的 EvalDataset（跨机器可复现）。

    百万级语料（如 MMarco）必须抽样。抽样参数（n_queries/seed/
    distractor_ratio）必须记入报表，否则分数不可比。

    Args:
        ds: 原始数据集。
        n_queries: 抽中的 query 数；>= 全量时返回原数据集（同一对象）。
        seed: 随机种子，固定即可复现。
        distractor_ratio: 混入的无关 chunk 数量与相关 chunk 总数之比。
            仅保留相关 chunk 的候选池没有任何干扰项，检索指标会虚高，
            正式评测务必 > 0；0.0 仅供快速调试。
        full_corpus: True 时切换「全库口径」——候选池保留完整 corpus
            （与 MTEB/BEIR 全库排名口径对齐，绝对分可向榜单锚定），
            仅抽 query；distractor_ratio 语义失效（全库即最大干扰池）。

    Returns:
        新 EvalDataset，name 追加 "-sampled{n}-seed{s}-dr{r}" 或
        "-fullcorpus-seed{s}" 后缀以标识抽样参数，便于追溯。
    """
    if full_corpus:
        if n_queries >= len(ds.queries):
            kept = sorted(ds.queries)
        else:
            rng = random.Random(seed)
            kept = rng.sample(sorted(ds.queries), n_queries)
        queries = {qid: ds.queries[qid] for qid in kept}
        qrels = {qid: ds.qrels[qid] for qid in kept if qid in ds.qrels}
        name = f"{ds.name}-fullcorpus-seed{seed}"
        return EvalDataset(name=name, corpus=dict(ds.corpus), queries=queries, qrels=qrels)

    if n_queries >= len(ds.queries):
        return ds

    rng = random.Random(seed)
    kept = rng.sample(sorted(ds.queries), n_queries)

    queries = {qid: ds.queries[qid] for qid in kept}
    qrels = {qid: ds.qrels[qid] for qid in kept if qid in ds.qrels}

    relevant_ids = {cid for rel in qrels.values() for cid in rel}
    n_distractors = int(round(len(relevant_ids) * distractor_ratio))
    distractors: set[str] = set()
    if n_distractors > 0:
        pool = sorted(set(ds.corpus) - relevant_ids)
        distractors = set(rng.sample(pool, min(n_distractors, len(pool))))

    corpus = {cid: ds.corpus[cid] for cid in relevant_ids | distractors}
    name = f"{ds.name}-sampled{n_queries}-seed{seed}-dr{distractor_ratio}"
    return EvalDataset(name=name, corpus=corpus, queries=queries, qrels=qrels)
