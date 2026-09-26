"""数据库结构引导（幂等）。

背景：本项目的 Alembic 初始迁移是空壳（``pass``），**无法从空库把结构建出来**——
开发环境一直靠应用启动时的 ``create_all`` 兜底，这个隐式行为在全新部署时暴露为
故障（迁移链中途报 ``relation "users" does not exist``）。

在补出真正的基线迁移之前，这里把隐式行为显式化，让"一条命令把库建到最新结构"成立：

1. 空库            → 按 ORM 模型建全表，再把版本标记为 head
2. 有表但没版本标记 → 只补打版本标记（历史开发库）
3. 已有版本标记     → 正常 ``alembic upgrade head``

长期正确做法是把基线迁移补成真能建表的 DDL，届时情形 1 应改为直接 upgrade。

实现约束：Alembic 的 ``env.py`` 内部自己 ``asyncio.run``，因此**不能在本模块的
事件循环里直接调用 ``alembic.command``**（会撞上"asyncio.run() cannot be called
from a running event loop"，表现为迁移没执行且协程未被等待）。所有 alembic 操作
一律通过子进程走命令行，与文档和 CI 的用法保持一致。
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.database import Base

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]

# (状态, 后续需要在事件循环外执行的 alembic 动作)
Action = str  # "none" | "upgrade" | "stamp"


async def _probe() -> tuple[bool, bool]:
    """返回 (有版本标记, 有业务表)。用临时引擎，不碰应用连接池。"""
    engine = create_async_engine(settings.database_url)
    try:

        def _inspect(sync_conn):
            names = set(inspect(sync_conn).get_table_names())
            return ("alembic_version" in names, bool(names - {"alembic_version"}))

        async with engine.connect() as conn:
            return await conn.run_sync(_inspect)
    finally:
        await engine.dispose()


async def _create_all() -> None:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _decide() -> tuple[str, Action]:
    """判定当前库处于哪种情形，返回 (情形标签, 待执行的 alembic 动作)。"""
    if make_url(settings.database_url).get_backend_name() == "sqlite":
        # 测试/嵌入式场景：没有独立 server，直接按模型建表即可
        await _create_all()
        return "sqlite-create-all", "none"

    versioned, has_tables = await _probe()
    if versioned:
        return "versioned", "upgrade"
    if has_tables:
        return "tables-without-version", "stamp"
    await _create_all()
    return "empty-bootstrapped", "stamp"


def _run_alembic(verb: str) -> None:
    """在事件循环外以子进程调用 alembic CLI。失败抛异常。"""
    result = subprocess.run(  # noqa: S603 - 固定参数，无用户输入
        ["alembic", verb, "head"],  # noqa: S607 - 容器内 PATH 中的 alembic
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"alembic {verb} head 失败（退出码 {result.returncode}）：{detail[-800:]}")


def run() -> str:
    """执行引导，返回情形标签。异常向上抛，由入口决定退不退。"""
    case, action = asyncio.run(_decide())
    if action != "none":
        _run_alembic(action)
    return f"{case}+{action}"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        summary = run()
    except Exception as exc:  # noqa: BLE001 - 引导失败必须让容器退出而不是带病启动
        logger.error("schema bootstrap failed: %s", exc)
        return 1
    logger.info("schema bootstrap done: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
