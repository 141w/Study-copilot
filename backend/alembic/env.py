import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from app.db.database import Base

target_metadata = Base.metadata

# Import all models to ensure they are registered with Base.metadata

# 解析数据库 URL（修复 2026-08-19）：
# 1) 环境变量 DATABASE_URL 优先（docker-compose 已注入，指向 db 服务）
# 2) 否则读 app settings（pydantic-settings 会加载 backend/.env）——
#    旧实现只看环境变量，容器外手动跑 alembic 时 .env 不生效，
#    容器内忘设环境变量时则静默 fallback 到 alembic.ini 的 localhost 默认值（连错库）
from_env = os.getenv("DATABASE_URL")
if from_env:
    config.set_main_option("sqlalchemy.url", from_env)
else:
    from app.config import settings

    config.set_main_option("sqlalchemy.url", settings.database_url)

# Fail-fast：容器内解析出 localhost 意味着会连到容器自身而非 db 服务
_final_url = config.get_main_option("sqlalchemy.url") or ""
if "localhost" in _final_url and os.path.exists("/.dockerenv"):
    raise RuntimeError(
        "alembic 在容器内解析到 localhost 数据库地址，这会连接到容器自身而不是 db 服务。"
        "请设置 DATABASE_URL 环境变量，例如："
        "postgresql+asyncpg://study_user:study123@db:5432/study_copilot"
    )

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
