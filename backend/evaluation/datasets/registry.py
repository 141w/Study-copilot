"""数据集注册表：名称 -> adapter。"""

from __future__ import annotations

from collections.abc import Callable

from evaluation.datasets.base import EvalDataset
from evaluation.datasets.cmedqa import load_cmedqa
from evaluation.datasets.crudrag import load_crudrag
from evaluation.datasets.financeqa import load_financeqa
from evaluation.datasets.mmarco import load_mmarco

LOADERS: dict[str, Callable[..., EvalDataset]] = {
    "mmarco": load_mmarco,
    "cmedqa": load_cmedqa,
    "financeqa": load_financeqa,
    "crudrag": load_crudrag,  # 实验性：HF 候选不可用时抛错并给全库口径 fallback 指引
}

DATASET_NAMES = tuple(LOADERS)


def load_eval_dataset(
    name: str,
    n_queries: int,
    seed: int,
    distractor_ratio: float,
    full_corpus: bool = False,
) -> EvalDataset:
    """按名称加载数据集并抽样。

    Args:
        full_corpus: True 时候选池保留全库（对齐 MTEB/BEIR 口径），
            仅抽 query。各 adapter 内部透传 sample_dataset。

    Raises:
        KeyError: 未知数据集名。
    """
    return LOADERS[name](
        n_queries=n_queries, seed=seed, distractor_ratio=distractor_ratio, full_corpus=full_corpus
    )
