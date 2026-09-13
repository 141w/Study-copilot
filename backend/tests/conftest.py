import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app

# 使用 SQLite 作为测试数据库（无需 PostgreSQL）
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
# 与 settings.embedding_dimension / 文档向量列一致
FAKE_EMBED_DIM = 768


class _FakeEmbedder:
    """CI / 离线环境用的轻量 embedder 占位（接口与 app.core.embedder.embedder 对齐）。

    真实模型仅在本机已缓存、且未设置 HF_HUB_OFFLINE/CI 时才需要；
    单元测试关注业务编排，不应依赖 HuggingFace 下载。
    """

    model_name = "fake/test-embedder"
    dimension = FAKE_EMBED_DIM

    @property
    def model(self):
        # system_status 等探活代码会读 embedder.model
        return object()

    def _vec(self, seed: str) -> list[float]:
        # 确定性伪向量：同文本 → 同向量，便于断言
        h = abs(hash(seed)) % (2**32)
        return [((h >> (i % 32)) & 1) * 0.1 + (i % 7) * 0.01 for i in range(FAKE_EMBED_DIM)]

    async def embed_query(self, text: str):
        import numpy as np

        return np.array(self._vec(text or ""), dtype="float32")

    async def embed_texts(self, texts: list[str]):
        import numpy as np

        return np.array([self._vec(t or "") for t in texts], dtype="float32")

    def encode(self, texts, **kwargs):
        import numpy as np

        if isinstance(texts, str):
            return np.array(self._vec(texts), dtype="float32")
        return np.array([self._vec(t or "") for t in texts], dtype="float32")

    def ensure_loaded(self):
        return None


def _should_mock_embedder() -> bool:
    return os.environ.get("HF_HUB_OFFLINE") == "1" or os.environ.get("CI") == "true"


@pytest.fixture(autouse=True)
async def _fake_embedder_in_ci(monkeypatch):
    """HF_HUB_OFFLINE=1 或 CI 时替换全局 embedder，避免 Runner 拉模型。"""
    if not _should_mock_embedder():
        yield
        return
    import app.core.embedder as emb_mod

    fake = _FakeEmbedder()
    monkeypatch.setattr(emb_mod, "embedder", fake)
    # 常见 from-import 站点
    for mod_name in (
        "app.services.chat_service",
        "app.services.document_service",
        "app.services.note_service",
        "app.core.pgvector_store",
        "app.core.vector_store",
    ):
        try:
            mod = __import__(mod_name, fromlist=["embedder"])
            if hasattr(mod, "embedder"):
                monkeypatch.setattr(mod, "embedder", fake)
        except Exception:
            pass
    yield


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables(test_engine):
    """每个测试结束后清空全部业务表。

    session 级引擎意味着所有测试共享同一个 SQLite 库；不清理时，
    前序测试遗留的固定主键（用户/任务 id）会让后续测试撞
    UNIQUE/FK 约束，且只在全量跑时暴露（单文件跑是干净库，
    这正是 2026-08-27 之前"单独绿、全量炸"的根因）。
    """
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
