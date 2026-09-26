"""评测统一环境入口：收敛此前散落在 5 个脚本头部的 DATABASE_URL/HF 缓存硬编码。

必须在 import app.* 之前调用 ensure_eval_env()：app.db 的引擎在 import 时
绑定 settings.DATABASE_URL，晚设无效。

优先级：EVAL_DATABASE_URL > DATABASE_URL > 内置评测库缺省。
CI 双实例（simple / zh）通过切 EVAL_DATABASE_URL 或连接串注入实现，
评测代码零改动。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_EVAL_DATABASE_URL = "postgresql+asyncpg://eval@127.0.0.1:55432/evaldb"

# 数据集下载缓存默认重定向到 evaluation/data/（gitignored），避免污染 ~/.cache
_DEFAULT_HF_DATASETS_CACHE = Path(__file__).resolve().parent / "data" / "hf-datasets"


def ensure_eval_env() -> None:
    """预设置评测所需环境变量（不覆盖显式传入的值）。"""
    url = os.environ.get("EVAL_DATABASE_URL") or os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url or DEFAULT_EVAL_DATABASE_URL
    os.environ.setdefault("HF_DATASETS_CACHE", str(_DEFAULT_HF_DATASETS_CACHE))
