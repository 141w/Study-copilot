"""检索指标计算与聚合 runner（纯 stdlib，无重依赖）。

指标定义（k = 截断深度，relevant = qrels 中 relevance > 0 的 chunk 集合）：

- Recall@k   = |top-k ∩ relevant| / |relevant|          该捞的捞全了吗（最严格）
- HitRate@k  = 1 if top-k ∩ relevant else 0             口语常说的「召回率」
- MRR@k      = 1 / rank(第一个命中的相关项)               排序质量
- nDCG@k     = DCG@k / IDCG@k（支持分级 relevance）       排序综合质量
- CP@k       = Σ P@i·rel_i / min(k,|relevant|)           相关项密度与位置（AP@k）

指标在 query 粒度计算后取算术平均；无相关标注的 query 不参与统计
（分母为 0 无意义）。分数可比性要求：同一次对比必须同数据集、同抽样
参数、同 k 值集合——报表须记录全部运行参数。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

K_VALUES: tuple[int, ...] = (1, 5, 10, 100)


def _relevant(gains: Mapping[str, int]) -> set[str]:
    """relevance > 0 的 chunk 集合。"""
    return {cid for cid, g in gains.items() if g > 0}


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """|top-k ∩ relevant| / |relevant|；relevant 为空时返回 0.0。"""
    if not relevant:
        return 0.0
    hits = sum(1 for cid in retrieved[:k] if cid in relevant)
    return hits / len(relevant)


def hit_rate_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """top-k 命中任意相关项则为 1.0，否则 0.0。"""
    return 1.0 if any(cid in relevant for cid in retrieved[:k]) else 0.0


def mrr_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """第一个命中的相关项排名的倒数（top-k 之外视为未命中）。"""
    for i, cid in enumerate(retrieved[:k]):
        if cid in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], gains: Mapping[str, int], k: int) -> float:
    """分级 nDCG@k（2^g - 1 增益，二值时退化为标准二进制 nDCG）。

    IDCG 为按 relevance 降序的理想排序；理想增益为 0 时返回 0.0
    （该 query 无相关标注，调用方应已在聚合层跳过）。
    """
    dcg = 0.0
    for i, cid in enumerate(retrieved[:k]):
        g = gains.get(cid, 0)
        if g > 0:
            dcg += (2.0**g - 1.0) / math.log2(i + 2)
    ideal = sorted((g for g in gains.values() if g > 0), reverse=True)[:k]
    idcg = sum((2.0**g - 1.0) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def context_precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """平均精度截断到 k：Σ P@i·rel_i / min(k, |relevant|)（top-k 之外的命中不计）。

    与 RAGAS context_precision 同构：RAGAS 把 rel_i 换成 LLM 判定
    「该 context 是否支持参考答案」，本实现用 qrels 二值判定；
    两者方向互证、数值不可直接比。衡量排序中相关项的密度与位置，
    对 rerank/融合类改动尤其敏感。
    """
    if not relevant:
        return 0.0
    hits = 0
    ap = 0.0
    for i, cid in enumerate(retrieved[:k]):
        if cid in relevant:
            hits += 1
            ap += hits / (i + 1)
    denom = min(k, len(relevant))
    return ap / denom if denom > 0 else 0.0


@dataclass
class Metrics:
    """单次评测（一个数据集 × 一个检索方法）的聚合结果。"""

    name: str
    n_queries: int
    recall: dict[int, float] = field(default_factory=dict)
    hit_rate: dict[int, float] = field(default_factory=dict)
    mrr: dict[int, float] = field(default_factory=dict)
    ndcg: dict[int, float] = field(default_factory=dict)
    ctx_precision: dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """序列化为 JSON 友好结构（k 转字符串，浮点保留 4 位）。"""
        return {
            "name": self.name,
            "n_queries": self.n_queries,
            "recall": {str(k): round(v, 4) for k, v in self.recall.items()},
            "hit_rate": {str(k): round(v, 4) for k, v in self.hit_rate.items()},
            "mrr": {str(k): round(v, 4) for k, v in self.mrr.items()},
            "ndcg": {str(k): round(v, 4) for k, v in self.ndcg.items()},
            "ctx_precision": {str(k): round(v, 4) for k, v in self.ctx_precision.items()},
        }

    def summary_line(self) -> str:
        """单行可读摘要（日志/终端）。"""
        ks = sorted(self.recall)
        ks_str = ", ".join(str(k) for k in ks)
        parts = [
            f"queries={self.n_queries}",
            f"recall@{ks_str}=[{', '.join(f'{self.recall[k]:.4f}' for k in ks)}]",
            f"hit@{ks_str}=[{', '.join(f'{self.hit_rate[k]:.4f}' for k in ks)}]",
            f"mrr@{ks_str}=[{', '.join(f'{self.mrr[k]:.4f}' for k in ks)}]",
            f"ndcg@{ks_str}=[{', '.join(f'{self.ndcg[k]:.4f}' for k in ks)}]",
            f"cp@{ks_str}=[{', '.join(f'{self.ctx_precision.get(k, 0.0):.4f}' for k in ks)}]",
        ]
        return f"[{self.name}] " + " ".join(parts)


def evaluate_retrieval(
    name: str,
    run: Mapping[str, Sequence[str]],
    qrels: Mapping[str, Mapping[str, int]],
    k_values: Sequence[int] = K_VALUES,
) -> Metrics:
    """对一次检索结果（run）在 qrels 标注下计算聚合指标。

    Args:
        name: 报表名称（如 "mmarco-hybrid"）。
        run: query_id -> 按排名降序的 chunk_id 列表；缺失的 query 视为未召回。
        qrels: query_id -> {chunk_id: relevance}。
        k_values: 截断深度集合，默认 (1, 5, 10, 100)。

    Returns:
        Metrics 聚合结果。

    Raises:
        ValueError: 无任何可评估 query（全部缺 run 或无相关标注）。
    """
    ks = tuple(sorted(set(k_values)))
    buckets: dict[str, list[float]] = {
        f"{metric}@{k}": [] for metric in ("recall", "hit", "mrr", "ndcg", "cp") for k in ks
    }

    n = 0
    for qid, gains in qrels.items():
        relevant = _relevant(gains)
        if not relevant:
            continue  # 无相关标注的 query 不参与统计
        retrieved = list(run.get(qid, []))
        n += 1
        for k in ks:
            buckets[f"recall@{k}"].append(recall_at_k(retrieved, relevant, k))
            buckets[f"hit@{k}"].append(hit_rate_at_k(retrieved, relevant, k))
            buckets[f"mrr@{k}"].append(mrr_at_k(retrieved, relevant, k))
            buckets[f"ndcg@{k}"].append(ndcg_at_k(retrieved, gains, k))
            buckets[f"cp@{k}"].append(context_precision_at_k(retrieved, relevant, k))

    if n == 0:
        raise ValueError("no evaluable queries: every query lacks run results or relevant labels")

    def _mean(key: str) -> float:
        vals = buckets[key]
        return sum(vals) / len(vals)

    return Metrics(
        name=name,
        n_queries=n,
        recall={k: _mean(f"recall@{k}") for k in ks},
        hit_rate={k: _mean(f"hit@{k}") for k in ks},
        mrr={k: _mean(f"mrr@{k}") for k in ks},
        ndcg={k: _mean(f"ndcg@{k}") for k in ks},
        ctx_precision={k: _mean(f"cp@{k}") for k in ks},
    )
