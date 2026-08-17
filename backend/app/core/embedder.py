import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """
    Embedding 模块（异步化 + 增量缓存）。

    改进点（2025-05-13）：
    1. encode() 放入 asyncio.to_thread 避免阻塞事件循环
    2. 增加 (text_hash -> vector) 的本地缓存，支持增量更新
    """

    def __init__(self, model_name=None, cache_dir: str = "./.embedding_cache"):
        self.model_name = model_name or settings.embedding_model
        self.dimension = settings.embedding_dimension
        self._model = None
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict = {}
        self._load_cache()

    @property
    def model(self):
        if self._model is None:
            try:
                # 支持通过 HF_ENDPOINT 环境变量使用 HuggingFace 镜像
                # 例如：export HF_ENDPOINT=https://hf-mirror.com
                hf_endpoint = os.environ.get("HF_ENDPOINT")
                if hf_endpoint:
                    os.environ.setdefault(
                        "HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
                    )
                    # sentence-transformers 底层使用 huggingface_hub，会自动读取 HF_ENDPOINT
                    logger.info(f"Using HuggingFace mirror endpoint: {hf_endpoint}")

                logger.info(f"Loading embedding model: {self.model_name}")
                model_kwargs = {}
                if os.environ.get("HF_HUB_OFFLINE") == "1":
                    model_kwargs["local_files_only"] = True
                self._model = SentenceTransformer(self.model_name, **model_kwargs)
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise RuntimeError(
                    f"无法加载 Embedding 模型 '{self.model_name}'。请尝试以下方法：\n"
                    f"  1. 检查网络连接，确保能访问 HuggingFace\n"
                    f"  2. 设置镜像：export HF_ENDPOINT=https://hf-mirror.com\n"
                    f"  3. 手动下载模型到本地：huggingface-cli download {self.model_name}\n"
                    f"  4. 设置离线模式（如果已下载）：export HF_HUB_OFFLINE=1\n"
                    f"原始错误: {e}"
                ) from e
        return self._model

    def ensure_loaded(self):
        """预加载模型，确保在请求时不需首次下载"""
        return self.model

    def reload_model(self, model_name: str, dimension: int):
        """切换 Embedding 模型：清除当前模型，更新参数，下次访问时懒加载新模型"""
        if model_name == self.model_name and dimension == self.dimension:
            return
        logger.info(
            f"Switching embedding model: {self.model_name} -> {model_name}, dimension: {self.dimension} -> {dimension}"
        )
        self._model = None
        self.model_name = model_name
        self.dimension = dimension
        # 维度可能不同，清空缓存避免向量不兼容
        self._cache = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # 缓存机制
    # ------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        """基于文本内容生成缓存键"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def _cache_file(self) -> Path:
        """缓存文件路径"""
        model_slug = self.model_name.replace("/", "__")
        return self._cache_dir / f"{model_slug}.json"

    def _load_cache(self):
        """从磁盘加载缓存（只加载键，不加载大向量文件）"""
        cf = self._cache_file()
        if cf.exists():
            try:
                with open(cf, encoding="utf-8") as f:
                    data = json.load(f)
                # 反序列化：将 list 转回 numpy
                loaded = {}
                for k, v in data.items():
                    if isinstance(v, list):
                        loaded[k] = np.array(v, dtype=np.float32)
                self._cache = loaded
                logger.info(f"Embedding cache loaded: {len(self._cache)} entries")
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")
                self._cache = {}

    def _save_cache(self):
        """将缓存持久化到磁盘"""
        try:
            cf = self._cache_file()
            # 序列化 numpy -> list
            data = {k: v.tolist() for k, v in self._cache.items()}
            with open(cf, "w", encoding="utf-8") as f:
                json.dump(data, f)
            logger.info(f"Embedding cache saved: {len(self._cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")

    # ------------------------------------------------------------------
    # 异步 Embedding
    # ------------------------------------------------------------------

    async def embed_texts(self, texts: list[str]) -> np.ndarray:
        """异步批量获取 Embedding（带缓存）"""
        if not texts:
            return np.array([])

        # 命中缓存的复用，未命中的计算
        to_compute = []
        to_compute_idx = []
        results = [None] * len(texts)

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                results[i] = self._cache[key]
            else:
                to_compute.append(text)
                to_compute_idx.append(i)

        if to_compute:
            # 异步执行 CPU 密集型 encode（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            embs = await loop.run_in_executor(
                None,  # 默认线程池
                lambda: self.model.encode(
                    to_compute, convert_to_numpy=True, show_progress_bar=False
                ),
            )
            # 写入缓存
            for idx_in_compute, text in enumerate(to_compute):
                key = self._cache_key(text)
                vec = embs[idx_in_compute]
                self._cache[key] = vec
                results[to_compute_idx[idx_in_compute]] = vec

            # 异步保存缓存（不阻塞主流程）
            asyncio.create_task(asyncio.to_thread(self._save_cache))

        # 统一转换为 numpy ndarray
        return np.stack(results)

    async def embed_query(self, query: str) -> np.ndarray:
        """异步获取单条查询 Embedding"""
        arr = await self.embed_texts([query])
        return arr[0]


embedder = Embedder()
