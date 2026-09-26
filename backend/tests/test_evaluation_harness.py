"""evaluation 评测脚手架的单测。

覆盖范围：
- harness 指标计算（Recall/HitRate/MRR/nDCG，含分级 relevance）
- evaluate_retrieval 聚合与边界（无标注 query 跳过、空 run 报错）
- datasets.base 抽样（可复现性、distractor 混入、qrels 校验）

评测脚手架本身的正确性测试：纯计算、无网络/DB/embedder 依赖，
可安全进常规 CI 套件（不触碰 app/，不改变 65% 覆盖率门禁）。
"""

from __future__ import annotations

import pytest

from evaluation.datasets.base import EvalDataset, sample_dataset
from evaluation.harness import (
    evaluate_retrieval,
    hit_rate_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)

LOG2_3 = 1.584962500721156  # log2(3)


# ---------------------------------------------------------------- 指标计算

def test_recall_at_k_counts_all_relevant():
    assert recall_at_k(["a", "b", "c"], {"a", "d"}, 3) == 0.5
    assert recall_at_k(["a", "b", "c"], {"a", "d"}, 2) == 0.5
    assert recall_at_k(["x", "y", "a"], {"a"}, 3) == 1.0
    assert recall_at_k(["x", "y"], {"a"}, 3) == 0.0
    assert recall_at_k(["a"], set(), 1) == 0.0  # 无标注相关项


def test_hit_rate_at_k():
    assert hit_rate_at_k(["x", "a"], {"a"}, 2) == 1.0
    assert hit_rate_at_k(["x", "y"], {"a"}, 2) == 0.0
    assert hit_rate_at_k(["x", "a"], {"a"}, 1) == 0.0  # 第 1 位不算命中


def test_mrr_at_k():
    assert mrr_at_k(["a", "b"], {"b"}, 5) == 0.5
    assert mrr_at_k(["x", "y"], {"a"}, 5) == 0.0
    assert mrr_at_k(["a"], {"a"}, 1) == 1.0


def test_ndcg_at_k_binary():
    # 相关项排第 1 位 → 满分
    assert ndcg_at_k(["a", "b"], {"a": 1}, 2) == pytest.approx(1.0)
    # 相关项排第 2 位 → 1/log2(3)
    assert ndcg_at_k(["x", "a"], {"a": 1}, 2) == pytest.approx(1.0 / LOG2_3)


def test_ndcg_at_k_graded_rewards_ranking():
    # 高 gain(2) 排第 1、低 gain(1) 排第 2 → 理想排序，满分
    assert ndcg_at_k(["high", "low"], {"high": 2, "low": 1}, 2) == pytest.approx(1.0)
    # 反之：低 gain 排第 1、高 gain 排第 2 → 低于满分
    assert ndcg_at_k(["low", "high"], {"high": 2, "low": 1}, 2) < 1.0
    # 无标注 → 0.0
    assert ndcg_at_k(["a"], {"a": 0}, 1) == 0.0


# ---------------------------------------------------------------- 聚合

def test_evaluate_retrieval_aggregates_over_queries():
    qrels = {"q1": {"c1": 1}, "q2": {"c2": 1}, "q3": {}}  # q3 无标注
    run = {"q1": ["c1", "c2"], "q2": ["c3", "c2"], "q3": ["c1"]}
    m = evaluate_retrieval("demo", run, qrels, k_values=(1, 5, 10))

    assert m.n_queries == 2  # q3 被跳过
    # q1: recall/hit/mrr = 1/1/1；q2: recall=1, hit@1=0, mrr=0.5
    assert m.recall[10] == pytest.approx(1.0)
    assert m.hit_rate[1] == pytest.approx(0.5)
    assert m.mrr[10] == pytest.approx(0.75)
    # ndcg@10 = (1.0 + 1/log2(3)) / 2：q1 相关项排第 1，q2 排第 2
    assert m.ndcg[10] == pytest.approx((1.0 + 1.0 / LOG2_3) / 2)


def test_evaluate_retrieval_raises_when_nothing_evaluable():
    with pytest.raises(ValueError, match="no evaluable queries"):
        evaluate_retrieval("empty", {}, {"q1": {}}, k_values=(1,))


def test_evaluate_retrieval_missing_run_counts_as_miss():
    m = evaluate_retrieval("demo", {}, {"q1": {"c1": 1}}, k_values=(1,))
    assert m.n_queries == 1
    assert m.recall[1] == 0.0
    assert m.hit_rate[1] == 0.0


def test_metrics_serialization_and_summary():
    m = evaluate_retrieval(
        "demo", {"q1": ["c1"]}, {"q1": {"c1": 1}}, k_values=(1, 5, 10)
    )
    d = m.to_dict()
    assert d["n_queries"] == 1
    assert d["recall"]["10"] == 1.0
    assert set(d["hit_rate"]) == {"1", "5", "10"}
    line = m.summary_line()
    assert line.startswith("[demo]")
    assert "recall@1, 5, 10=" in line


# ---------------------------------------------------------------- 抽样

def _make_dataset(n_queries: int, n_chunks: int) -> EvalDataset:
    """q_i 的唯一相关 chunk 为 c_i，其余 chunk 为候选干扰项。"""
    return EvalDataset(
        name="demo",
        corpus={f"c{i}": f"chunk-{i}" for i in range(n_chunks)},
        queries={f"q{i}": f"query-{i}" for i in range(n_queries)},
        qrels={f"q{i}": {f"c{i}": 1} for i in range(n_queries)},
    )


def test_sample_dataset_is_deterministic_for_same_seed():
    ds = _make_dataset(50, 50)
    a = sample_dataset(ds, n_queries=10, seed=7)
    b = sample_dataset(ds, n_queries=10, seed=7)
    assert set(a.queries) == set(b.queries)
    assert "-seed7" in a.name


def test_sample_dataset_differs_across_seeds():
    ds = _make_dataset(50, 50)
    a = sample_dataset(ds, n_queries=10, seed=7)
    b = sample_dataset(ds, n_queries=10, seed=8)
    assert set(a.queries) != set(b.queries)


def test_sample_dataset_full_returns_original():
    ds = _make_dataset(10, 10)
    assert sample_dataset(ds, n_queries=10) is ds


def test_sample_dataset_distractors_inflate_corpus():
    ds = _make_dataset(50, 100)  # 50 query / 100 chunk，抽 10 条 query
    without = sample_dataset(ds, n_queries=10, seed=1, distractor_ratio=0.0)
    with_dr = sample_dataset(ds, n_queries=10, seed=1, distractor_ratio=1.0)
    assert len(without.corpus) == 10  # 仅相关 chunk
    assert len(with_dr.corpus) == 20  # 相关 10 + 干扰 10
    # 干扰项只进 corpus，不进 qrels
    for qid, rel in with_dr.qrels.items():
        assert set(rel) == {f"c{qid[1:]}"}


def test_eval_dataset_rejects_dangling_qrels():
    with pytest.raises(ValueError, match="unknown queries"):
        EvalDataset(name="bad", corpus={"c1": "x"}, queries={}, qrels={"q1": {"c1": 1}})
    with pytest.raises(ValueError, match="unknown chunks"):
        EvalDataset(name="bad", corpus={}, queries={"q1": "x"}, qrels={"q1": {"c1": 1}})
