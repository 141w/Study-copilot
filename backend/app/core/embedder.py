from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import logging
import os
from app.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(self, model_name=None):
        self.model_name = model_name or settings.embedding_model
        self.dimension = settings.embedding_dimension
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                logger.info(f"Loading embedding model: {self.model_name}")
                model_kwargs = {}
                if os.environ.get("HF_HUB_OFFLINE") == "1":
                    model_kwargs["local_files_only"] = True
                self._model = SentenceTransformer(self.model_name, **model_kwargs)
                logger.info(f"Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._model

    def ensure_loaded(self):
        """预加载模型，确保在请求时不需首次下载"""
        return self.model

    async def embed_texts(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True)

    async def embed_query(self, query: str) -> np.ndarray:
        return self.model.encode([query], convert_to_numpy=True)[0]


embedder = Embedder()
