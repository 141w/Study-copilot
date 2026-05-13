"""
向量存储模块 - 抽象基类设计，符合开闭原则

架构：
- BaseVectorStore: 抽象基类，定义向量存储接口
- FAISSVectorStore: FAISS向量存储实现
- BM25VectorStore: BM25倒排索引实现（新增）
- HybridVectorStore: 混合检索实现（新增）

作者：AI全栈工程师
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
import pickle
import os
import json


class BaseVectorStore(ABC):
    """
    向量存储抽象基类
    
    设计原则：开闭原则 - 对扩展开放，对修改封闭
    子类只需实现接口方法，无需修改核心逻辑
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.chunks: List[Dict[str, Any]] = []
        self.document_ids: List[str] = []

    @abstractmethod
    async def add_chunks(self, chunks: List[Dict], doc_id: str) -> bool:
        """添加文本块到向量库"""
        pass

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索相似文本"""
        pass

    @abstractmethod
    async def save(self, path: str) -> bool:
        """保存向量库到磁盘"""
        pass

    @abstractmethod
    async def load(self, path: str) -> bool:
        """从磁盘加载向量库"""
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """删除向量库"""
        pass

    @abstractmethod
    def get_chunk_count(self) -> int:
        """获取块数量"""
        pass

    def _normalize_score(self, scores: np.ndarray) -> np.ndarray:
        """归一化分数到[0, 1]区间"""
        if scores.size == 0:
            return scores
        min_score, max_score = scores.min(), scores.max()
        if max_score - min_score == 0:
            return np.ones_like(scores)
        return (scores - min_score) / (max_score - min_score)


class FAISSVectorStore(BaseVectorStore):
    """
    FAISS向量存储实现
    
    使用余弦相似度（或L2距离）进行语义检索
    优点：支持语义相似度检索，检索精度高
    """

    def __init__(self, dimension: int = 384):
        super().__init__(dimension)
        self._index = None
        self._init_index()

    def _init_index(self):
        """初始化FAISS索引"""
        import faiss
        # 使用IndexFlatIP（内积）进行余弦相似度搜索
        # 先归一化向量，再使用内积等价于余弦相似度
        self._index = faiss.IndexFlatIP(self.dimension)

    async def add_chunks(self, chunks: List[Dict], doc_id: str) -> bool:
        """添加文本块"""
        if not chunks:
            return False

        from app.core.embedder import embedder
        
        texts = [c["text"] for c in chunks]
        embeddings = await embedder.embed_texts(texts)
        
        # 归一化向量（用于余弦相似度）
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = embeddings / norms

        self._index.add(embeddings)
        self.chunks.extend(chunks)
        self.document_ids.extend([doc_id] * len(chunks))
        
        return True

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """语义检索"""
        if self._index is None or self._index.ntotal == 0:
            return []

        from app.core.embedder import embedder
        
        q_emb = await embedder.embed_query(query)
        q_emb = q_emb.reshape(1, -1)
        
        # 归一化查询向量
        norm = np.linalg.norm(q_emb)
        if norm > 0:
            q_emb = q_emb / norm

        distances, indices = self._index.search(q_emb, min(top_k, self._index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(self.chunks):
                # 将距离转换为相似度（1 - 归一化距离）
                similarity = max(0, dist)
                results.append({
                    "chunk": self.chunks[idx],
                    "distance": float(1 - similarity),  # 转换为距离用于兼容
                    "similarity": float(similarity),
                    "index": int(idx),
                })

        return results

    async def save(self, path: str) -> bool:
        """保存FAISS索引"""
        import faiss
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        faiss.write_index(self._index, f"{path}.index")
        
        with open(f"{path}.pkl", "wb") as f:
            pickle.dump({
                "chunks": self.chunks,
                "document_ids": self.document_ids,
                "dimension": self.dimension
            }, f)
        
        return True

    async def load(self, path: str) -> bool:
        """加载FAISS索引"""
        import faiss
        
        index_file = f"{path}.index"
        if not os.path.exists(index_file):
            return False
            
        try:
            self._index = faiss.read_index(index_file)
            
            with open(f"{path}.pkl", "rb") as f:
                data = pickle.load(f)
                self.chunks = data["chunks"]
                self.document_ids = data["document_ids"]
                self.dimension = data.get("dimension", self.dimension)
            
            return True
        except Exception:
            return False

    def delete(self, path: str) -> bool:
        """删除FAISS索引文件"""
        for ext in [".index", ".pkl"]:
            fp = f"{path}{ext}"
            if os.path.exists(fp):
                os.remove(fp)
        return True

    def get_chunk_count(self) -> int:
        """获取块数量"""
        return len(self.chunks)


class BM25VectorStore(BaseVectorStore):
    """
    BM25向量存储实现
    
    使用Okapi BM25算法进行词项检索
    优点：支持精确关键词检索，不依赖embedding模型
    """

    def __init__(self, dimension: int = 384):
        super().__init__(dimension)
        self._bm25 = None
        self._corpus: List[str] = []

    def _init_bm25(self):
        """初始化BM25"""
        from rank_bm25 import BM25Okapi
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)

    async def add_chunks(self, chunks: List[Dict], doc_id: str) -> bool:
        """添加文本块"""
        if not chunks:
            return False

        texts = [c["text"] for c in chunks]
        self._corpus.extend(texts)
        
        if self._bm25 is None:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            # 重新构建索引
            self._bm25 = BM25Okapi(self._corpus)

        self.chunks.extend(chunks)
        self.document_ids.extend([doc_id] * len(chunks))
        
        return True

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """BM25关键词检索"""
        if not self._bm25 or not self._corpus:
            return []

        # 分词处理
        import re
        tokens = re.findall(r'\w+', query.lower())
        
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        
        # 获取top_k索引
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if 0 <= idx < len(self.chunks):
                results.append({
                    "chunk": self.chunks[idx],
                    "distance": float(1 - scores[idx]),  # 兼容旧接口
                    "bm25_score": float(scores[idx]),
                    "index": int(idx),
                })

        return results

    async def save(self, path: str) -> bool:
        """保存BM25索引"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(f"{path}.bm25", "w", encoding="utf-8") as f:
            json.dump({
                "chunks": self.chunks,
                "document_ids": self.document_ids,
                "corpus": self._corpus
            }, f, ensure_ascii=False)
        
        return True

    async def load(self, path: str) -> bool:
        """加载BM25索引"""
        bm25_file = f"{path}.bm25"
        if not os.path.exists(bm25_file):
            return False
            
        try:
            with open(bm25_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.chunks = data["chunks"]
                self.document_ids = data["document_ids"]
                self._corpus = data["corpus"]
            
            if self._corpus:
                from rank_bm25 import BM25Okapi
                self._bm25 = BM25Okapi(self._corpus)
            
            return True
        except Exception:
            return False

    def delete(self, path: str) -> bool:
        """删除BM25索引文件"""
        bm25_file = f"{path}.bm25"
        if os.path.exists(bm25_file):
            os.remove(bm25_file)
        return True

    def get_chunk_count(self) -> int:
        """获取块数量"""
        return len(self.chunks)


class HybridVectorStore(BaseVectorStore):
    """
    混合检索向量库 - 结合FAISS和BM25
    
    使用RRF（Reciprocal Rank Fusion）算法融合两种检索结果
    优点：既支持语义检索，又支持关键词检索
    """

    def __init__(self, dimension: int = 384, faiss_weight: float = 0.5, bm25_weight: float = 0.5):
        super().__init__(dimension)
        
        # 创建子向量库
        self._faiss = FAISSVectorStore(dimension)
        self._bm25 = BM25VectorStore(dimension)
        
        # 融合权重
        self.faiss_weight = faiss_weight
        self.bm25_weight = bm25_weight
        
        # RRF参数
        self._rrf_k = 60  # RRF算法参数

    async def add_chunks(self, chunks: List[Dict], doc_id: str) -> bool:
        """同时添加到FAISS和BM25"""
        await self._faiss.add_chunks(chunks, doc_id)
        await self._bm25.add_chunks(chunks, doc_id)
        
        self.chunks.extend(chunks)
        self.document_ids.extend([doc_id] * len(chunks))
        
        return True

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """混合检索"""
        faiss_results = await self._faiss.search(query, top_k * 2)
        bm25_results = await self._bm25.search(query, top_k * 2)
        
        # RRF融合
        fused = self._rrf_fusion(faiss_results, bm25_results, top_k)
        
        return fused

    def _rrf_fusion(
        self, 
        faiss_results: List[Dict], 
        bm25_results: List[Dict],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        RRF (Reciprocal Rank Fusion) 算法
        
        RRF_score(d) = Σ 1 / (k + rank(d))
        其中k为常数（通常60），rank(d)为文档d在各结果列表中的排名
        """
        scores: Dict[int, float] = {}
        
        # 处理FAISS结果
        for rank, result in enumerate(faiss_results):
            idx = result["index"]
            score = self.faiss_weight * (1.0 / (self._rrf_k + rank + 1))
            scores[idx] = scores.get(idx, 0) + score
            
        # 处理BM25结果
        for rank, result in enumerate(bm25_results):
            idx = result["index"]
            score = self.bm25_weight * (1.0 / (self._rrf_k + rank + 1))
            scores[idx] = scores.get(idx, 0) + score
        
        # 按融合分数排序
        sorted_indices = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for idx, fused_score in sorted_indices:
            if 0 <= idx < len(self.chunks):
                results.append({
                    "chunk": self.chunks[idx],
                    "distance": 1 - fused_score,  # 兼容
                    "fused_score": fused_score,
                    "index": idx,
                    "retrieval_type": "hybrid"
                })
        
        return results

    async def save(self, path: str) -> bool:
        """保存混合索引"""
        # 确保chunks同步到子向量库
        self._faiss.chunks = self.chunks
        self._faiss.document_ids = self.document_ids
        self._bm25.chunks = self.chunks
        self._bm25.document_ids = self.document_ids
        
        await self._faiss.save(f"{path}_faiss")
        await self._bm25.save(f"{path}_bm25")
        
        return True

    async def load(self, path: str) -> bool:
        """加载混合索引"""
        faiss_ok = await self._faiss.load(f"{path}_faiss")
        bm25_ok = await self._bm25.load(f"{path}_bm25")
        
        # 如果FAISS加载成功，从FAISS获取chunks
        if faiss_ok:
            self.chunks = self._faiss.chunks
            self.document_ids = self._faiss.document_ids
            return True
        
        # 如果BM25加载成功，从BM25获取chunks
        if bm25_ok:
            self.chunks = self._bm25.chunks
            self.document_ids = self._bm25.document_ids
            return True
        
        return False

    def delete(self, path: str) -> bool:
        """删除混合索引"""
        self._faiss.delete(f"{path}_faiss")
        self._bm25.delete(f"{path}_bm25")
        
        meta_file = f"{path}.meta"
        if os.path.exists(meta_file):
            os.remove(meta_file)
        
        return True

    def get_chunk_count(self) -> int:
        """获取块数量"""
        return max(
            self._faiss.get_chunk_count(),
            self._bm25.get_chunk_count()
        )


class DocumentVectorStore:
    """
    文档级向量库包装器
    
    为每个文档维护独立的向量库，支持多文档检索
    """
    
    # 支持的检索类型
    RETRIEVAL_TYPE_FAISS = "faiss"
    RETRIEVAL_TYPE_BM25 = "bm25"
    RETRIEVAL_TYPE_HYBRID = "hybrid"
    
    def __init__(
        self, 
        doc_id: str,
        vectorstore_dir: str = "./vectorstore",
        retrieval_type: str = RETRIEVAL_TYPE_FAISS
    ):
        self.doc_id = doc_id
        self.vectorstore_dir = vectorstore_dir
        self.retrieval_type = retrieval_type
        
        # 根据类型创建向量库
        if retrieval_type == self.RETRIEVAL_TYPE_BM25:
            self._store = BM25VectorStore()
        elif retrieval_type == self.RETRIEVAL_TYPE_FAISS:
            self._store = FAISSVectorStore()
        else:  # hybrid
            self._store = HybridVectorStore()

    def get_path(self) -> str:
        return os.path.join(self.vectorstore_dir, self.doc_id)

    async def add_chunks(self, chunks):
        await self._store.add_chunks(chunks, self.doc_id)
        return await self.save()

    async def search(self, query, top_k=5):
        await self.load()
        return await self._store.search(query, top_k)

    async def save(self):
        os.makedirs(self.vectorstore_dir, exist_ok=True)
        return await self._store.save(self.get_path())

    async def load(self):
        path = self.get_path()
        
        # 先尝试FAISS格式
        faiss_path = path
        if os.path.exists(f"{faiss_path}.index"):
            self._store = FAISSVectorStore()
            return await self._store.load(faiss_path)
        
        # 再尝试HYBRID格式
        if os.path.exists(f"{path}_faiss.index"):
            self._store = HybridVectorStore()
            return await self._store.load(path)
        
        # 再尝试BM25格式
        if os.path.exists(f"{path}.bm25"):
            self._store = BM25VectorStore()
            return await self._store.load(path)
        
        return False

    def delete(self):
        return self._store.delete(self.get_path())


# 导出默认实例
vector_store = FAISSVectorStore()