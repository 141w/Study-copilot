"""数据集适配层：各公开数据集 → 统一 EvalDataset 三元组。

已接入：无（P1 起逐个接入 mmarco / cmedqa / financeqa）。
公共抽象见 base.py。
"""

from evaluation.datasets.base import EvalDataset, sample_dataset

__all__ = ["EvalDataset", "sample_dataset"]
