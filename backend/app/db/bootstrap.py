"""数据库结构引导（幂等）。

背景：本项目的 Alembic 初始迁移是一个空壳（``pass``），因此**无法从空库
把结构建出来**——开发环境一直靠应用启动时的 ``create_all`` 兜底，这个隐式
行为在全新部署时才暴露为故障（迁移链中途报 ``relation "users" does not exist``）。

在补齐真正的基线迁移之前，这里把隐式行为显式化，让"一条命令把库建到最新结构"
成立。三种情形分别处理：

1. 空库            → 按 ORM 模型建全表，再把版本标记为 head
2. 有表但没版本标记 → 只补打版本标记（历史开发库）
3. 已有版本标记     → 正常 ``alembic upgrade head``

注意：走情形 1/2 时，结构来源是 ORM 模型而不是迁移脚本。长期正确做法是把
基线迁移补成真能建表的 DDL，届时本模块的情形 1 应改为直接 ``upgrade head``。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.database import Base

logger = logging.getLogger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _alembic_config():
    """构造 Alembic Config（复用项目 env.py，含 async URL 处理）。"""
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


async def _probe() -> tuple[bool, bool]:
    """返回 (有版本标记, 有业务表)。用独立的临时引擎，避免污染应用连接池。"""
    engine = create_async_engine(settings.database_url)
    try:
        def _inspect(sync_conn):
            names = set(inspect(sync_conn).get_table_names())
            return ("alembic_version" in names, bool(names - {"alembic_version"}))

        async with engine.connect() as conn:
            return await conn.run_sync(_inspect)
    finally:
        await engine.dispose()


def _stamp_head() -> None:
    from alembic import command

    command.stamp(_alembic_config(), "head")


def _upgrade_head() -> None:
    from alembic import command

    command.upgrade(_alembic_config(), "head")


async def _create_all() -> None:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def ensure_schema() -> str:
    """把数据库结构推进到最新，返回执行了哪种情形（供日志/测试断言）。"""
    # 方言差异：SQLite 下没有独立的 server 可连，直接按空库处理
    if make_url(settings.database_url).get_backend_name() == "sqlite":
        await _create_all()
        return "sqlite-create-all"

    versioned, has_tables = await _probe()
    if versioned:
        _upgrade_head()
        return "upgraded"
    if has_tables:
        # 历史开发库：结构由 create_all 建出，但从未打版本标记
        _stamp_head()
        return "stamped-existing"
    await _create_all()
    _stamp_head()
    return "bootstrapped-from-models"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = asyncio.run(ensure_schema())
    except Exception as exc:  # noqa: BLE001 - 引导失败必须让容器退出而不是带病启动
        logger.error("schema bootstrap failed: %s", exc)
        return 1
    logger.info("schema bootstrap done: %s", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
