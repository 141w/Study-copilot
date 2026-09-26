"""数据库引导（app/db/bootstrap）的行为约束。

重点锁两件事：
1. Alembic 必须以子进程方式调用——它的 env.py 内部自己 asyncio.run，
   在已有事件循环里直接调 alembic.command 会失败（这正是容器崩溃重启的成因）。
2. 空库要能靠模型建表 + 打版本标记走通，而不是依赖迁移链从零建表。
"""

from __future__ import annotations

import pytest

from app.db import bootstrap


def test_run_alembic_uses_subprocess_not_command_api(monkeypatch):
    """断言走 CLI 子进程，防止有人"顺手优化"成直接 import alembic.command。"""
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ARG001
        captured["cmd"] = cmd
        captured["cwd"] = str(kwargs.get("cwd"))

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        return _R()

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    bootstrap._run_alembic("upgrade")

    assert captured["cmd"] == ["alembic", "upgrade", "head"]
    assert captured["cwd"].endswith("backend")  # type: ignore[union-attr]


def test_run_alembic_raises_with_stderr(monkeypatch):
    class _R:
        returncode = 1
        stdout = ""
        stderr = "boom: relation users does not exist"

    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *a, **k: _R())
    with pytest.raises(RuntimeError) as exc:
        bootstrap._run_alembic("upgrade")
    assert "relation users does not exist" in str(exc.value)


@pytest.mark.asyncio
async def test_sqlite_backend_short_circuits_to_create_all(monkeypatch):
    """嵌入式/测试库不跑 alembic，只按模型建表。"""
    monkeypatch.setattr(bootstrap.settings, "database_url", "sqlite+aiosqlite:///./t.db")
    calls: list[str] = []

    async def fake_create_all():
        calls.append("create_all")

    monkeypatch.setattr(bootstrap, "_create_all", fake_create_all)
    case, action = await bootstrap._decide()
    assert case == "sqlite-create-all"
    assert action == "none"
    assert calls == ["create_all"]


@pytest.mark.asyncio
async def test_empty_postgres_bootstraps_then_stamps(monkeypatch):
    """空 PG 库：先按模型建表，再打版本标记（不能直接 upgrade 迁移链）。"""
    monkeypatch.setattr(
        bootstrap.settings, "database_url", "postgresql+asyncpg://u:p@localhost:5432/scratch"
    )
    # 空库：无版本表、无业务表
    monkeypatch.setattr(bootstrap, "_probe", _returning((False, False)))
    created: list[str] = []

    async def fake_create_all():
        created.append("create_all")

    monkeypatch.setattr(bootstrap, "_create_all", fake_create_all)
    case, action = await bootstrap._decide()
    assert case == "empty-bootstrapped"
    assert action == "stamp"
    assert created == ["create_all"]


@pytest.mark.asyncio
async def test_legacy_tables_without_version_get_stamped(monkeypatch):
    """历史开发库：有表但没版本标记，只补标记，不重复建表。"""
    monkeypatch.setattr(
        bootstrap.settings, "database_url", "postgresql+asyncpg://u:p@localhost:5432/legacy"
    )
    monkeypatch.setattr(bootstrap, "_probe", _returning((False, True)))
    called = False

    async def fake_create_all():
        nonlocal called
        called = True

    monkeypatch.setattr(bootstrap, "_create_all", fake_create_all)
    case, action = await bootstrap._decide()
    assert (case, action) == ("tables-without-version", "stamp")
    assert called is False


@pytest.mark.asyncio
async def test_versioned_postgres_upgrades(monkeypatch):
    monkeypatch.setattr(
        bootstrap.settings, "database_url", "postgresql+asyncpg://u:p@localhost:5432/live"
    )
    monkeypatch.setattr(bootstrap, "_probe", _returning((True, True)))
    case, action = await bootstrap._decide()
    assert (case, action) == ("versioned", "upgrade")


def _returning(value):
    """构造一个签名为 async def _probe() 的假函数。"""

    async def _coro():
        return value

    return _coro
