"""FinanceQA（英文 10-K 财务问答检索）adapter。

数据源 ``Joshua-Xia/FinanceQA``（split test，字段：context / question /
chain_of_thought / answer / ...）。MTEB/BEIR 无现成的 FinanceQA 检索子集，
本 adapter 自建三元组：

- queries: question（英文财务问题）
- corpus: 各题 context 按段落切分后的 passage（跨题天然形成干扰项，
  故 distractor_ratio 参数不适用，仅保留接口一致性）
- qrels: 含答案数值的 passage 为 gold；找不到数值时退化为与问题词面
  重合度最高的 passage（确定性回退）

gold 标注质量决定该数据集指标可信度，实现为纯规则（数值匹配），
上线前建议人工抽检。
"""

from __future__ import annotations

import random
import re

from evaluation.baselines.tokenize import tokenize
from evaluation.datasets.base import EvalDataset

REPO = "Joshua-Xia/FinanceQA"

_MIN_PASSAGE_LEN = 10
_MAX_PASSAGES_PER_Q = 60  # 每道题 context 的段落上限（控制语料规模）
_NUM_RE = re.compile(r"\d[\d,]*\.?\d*")


def _norm(text: str | None) -> str:
    """归一化：去空白与常见货币/括号符号，小写（None 安全）。"""
    return re.sub(r"[\s,$%()]", "", (text or "").lower())


def _answer_value(answer: str | None) -> str | None:
    """取答案中第一个数值（去千分位逗号），如 32095 形式。"""
    if not answer:
        return None
    m = _NUM_RE.search(answer.replace(",", ""))
    return m.group(0) if m else None


def _split_passages(context: str | None) -> list[str]:
    """按空行优先、单行兜底切分 context，过滤过短段落（None 安全）。"""
    if not context:
        return []
    parts = re.split(r"\n\s*\n", context)
    parts = [p.strip() for p in parts if len(p.strip()) >= _MIN_PASSAGE_LEN]
    if len(parts) < 5:  # 空行切分不足时退回单行
        parts = [p.strip() for p in context.split("\n") if len(p.strip()) >= _MIN_PASSAGE_LEN]
    return parts[:_MAX_PASSAGES_PER_Q]


def _fallback_gold(passages: list[str], question: str) -> int:
    """无数值命中时：与问题词面重合度最高的段落下标（确定性，平局取首个）。"""
    q_tokens = set(tokenize(question))
    best_idx, best_score = 0, -1.0
    for i, p in enumerate(passages):
        p_tokens = set(tokenize(p))
        if not p_tokens:
            continue
        score = len(q_tokens & p_tokens) / max(len(q_tokens), 1)
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx


def load_financeqa(
    n_queries: int = 300,
    seed: int = 42,
    distractor_ratio: float = 10.0,  # noqa: ARG001 - 跨题干扰项天然充足，参数仅保接口一致
    full_corpus: bool = False,  # noqa: ARG001 - corpus 随抽中问题构建，无独立候选池概念，仅保接口一致
) -> EvalDataset:
    """加载并构建 FinanceQA 检索三元组。

    Args:
        n_queries: 抽中的问题数。
        seed: 随机种子（固定可复现）。
        distractor_ratio: 忽略（跨题段落即干扰项）。
    """
    from datasets import load_dataset

    rows = list(load_dataset(REPO, split="test"))
    rng = random.Random(seed)
    kept = sorted(rng.sample(range(len(rows)), min(n_queries, len(rows))))

    corpus: dict[str, str] = {}
    queries: dict[str, str] = {}
    qrels: dict[str, dict[str, int]] = {}
    seen_text: dict[str, str] = {}  # 归一化文本前 200 字 -> 已分配的全局 chunk id

    for i in kept:
        row = rows[i]
        qid = f"fq{i}"
        passages = _split_passages(row["context"])
        if not passages:
            continue

        # 段落到全局 id 的映射（跨题去重，重复段落共享 id）
        local_to_global: list[str] = []
        for j, text in enumerate(passages):
            key = _norm(text)[:200]
            gid = seen_text.get(key)
            if gid is None:
                gid = f"fq{i}-p{j}"
                seen_text[key] = gid
                corpus[gid] = text
            local_to_global.append(gid)

        # gold：含答案数值的段落；否则词面重合回退
        ans = _answer_value(row["answer"])
        gold_local = [j for j, text in enumerate(passages) if ans and ans in _norm(text)]
        if not gold_local:
            gold_local = [_fallback_gold(passages, row["question"])]

        queries[qid] = row["question"] or ""
        qrels[qid] = {local_to_global[j]: 1 for j in gold_local}

    return EvalDataset(
        name=f"financeqa-n{len(queries)}-s{seed}",
        corpus=corpus,
        queries=queries,
        qrels=qrels,
    )
