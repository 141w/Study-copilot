"""
文本分块模块 - 支持固定分块和语义分块

功能：
1. FixedChunker: 基于句子和固定大小的分块
2. SemanticChunker: 基于语义边界的智能分块（新增）

作者：AI全栈工程师
"""

from typing import List, Dict, Any, Optional
import re
import numpy as np
from abc import ABC, abstractmethod


class BaseChunker(ABC):
    """分块器抽象基类"""

    @abstractmethod
    def chunk_document(self, pages: List[Dict], source_name: str = "doc") -> List[Dict[str, Any]]:
        """对文档进行分块"""
        pass


class FixedChunker(BaseChunker):
    """
    固定分块器 - 基于句子边界和固定大小的分块
    
    特点：
    - 按句子边界分割
    - 合并成指定大小的块
    - 支持重叠区域
    """

    def __init__(
        self, 
        chunk_size: int = 500, 
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def split_sentences(self, text: str) -> List[str]:
        """按句子分割文本"""
        sentences = []

        # 方法1: 匹配中英文句子结束符
        pattern = r'(?<=[.!?。！？;;；；])\s+'
        parts = re.split(pattern, text)

        # 方法2: 如果分割失败或不完整，按换行和段落分割
        if len(parts) < 2 or any(len(p) > 1000 for p in parts):
            parts = re.split(r'[\n\n]+', text)
            parts = [p.strip() for p in parts if p.strip()]

        # 方法3: 如果仍然只有很少的块，按单个换行分割
        if len(parts) < 2:
            parts = re.split(r'\n+', text)
            parts = [p.strip() for p in parts if p.strip()]

        # 方法4: 仍然太多，按固定字符数分割（后备方案）
        if len(parts) == 1 and len(parts[0]) > 500:
            chunk_size = 300
            for i in range(0, len(parts[0]), chunk_size):
                chunk = parts[0][i:i+chunk_size]
                if chunk.strip():
                    sentences.append(chunk.strip())
                if len(sentences) >= 50:
                    break
            return sentences if sentences else parts

        # 合并相邻的过短块
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 如果上一个块太短，合并
            if sentences and len(sentences[-1]) < 100:
                sentences[-1] = sentences[-1] + " " + part
            else:
                sentences.append(part)

        return [s.strip() for s in sentences if s.strip()]

    def split_text(self, text: str) -> List[str]:
        """将文本分成多个块"""
        sentences = self.split_sentences(text)
        
        chunks = []
        current = []
        size = 0

        for sent in sentences:
            sz = len(sent)
            
            # 如果当前块加上新句子超过大小限制，先保存当前块
            if size + sz > self.chunk_size and size >= self.min_chunk_size:
                chunks.append(" ".join(current))
                
                # 处理重叠
                ov = " ".join(current)
                if len(ov) > self.chunk_overlap:
                    current = [ov[-self.chunk_overlap:]]
                    size = len(ov[-self.chunk_overlap:])
                else:
                    current = []
                    size = 0

            current.append(sent)
            size += sz

        # 处理剩余内容
        if current:
            chunks.append(" ".join(current))

        return [c for c in chunks if c.strip()]

    def chunk_document(self, pages: List[Dict], source_name: str = "doc") -> List[Dict[str, Any]]:
        """对文档进行分块"""
        chunks = []
        chunk_id = 0

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page", 0)

            if not page_text or not page_text.strip():
                continue

            for chunk_text in self.split_text(page_text):
                if not chunk_text or len(chunk_text.strip()) < 10:
                    continue
                chunks.append({
                    "id": f"{source_name}_{chunk_id}",
                    "text": chunk_text,
                    "source": source_name,
                    "page": page_num,
                    "char_count": len(chunk_text),
                    "chunking_method": "fixed"
                })
                chunk_id += 1

        return chunks


class SemanticChunker(BaseChunker):
    """
    语义分块器 - 基于语义边界的智能分块
    
    特点：
    - 使用Embedding检测语义边界
    - 自动识别段落/主题变化
    - 生成更连贯的语义块
    
    算法：
    1. 将文本分成候选句子
    2. 计算相邻句子的语义相似度
    3. 在低相似度位置断开
    """

    def __init__(
        self,
        min_chunk_size: int = 200,
        max_chunk_size: int = 1000,
        similarity_threshold: float = 0.3,
        breakpoint_threshold: float = 0.25
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.similarity_threshold = similarity_threshold
        self.breakpoint_threshold = breakpoint_threshold

    def split_sentences(self, text: str) -> List[str]:
        """按句子分割"""
        pattern = r'(?<=[.!?。！？;;；；])\s+'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """获取多个文本的embedding"""
        from app.core.embedder import embedder
        
        embeddings = await embedder.embed_texts(texts)
        return [emb for emb in embeddings]

    async def _find_semantic_boundaries(
        self, 
        sentences: List[str]
    ) -> List[int]:
        """
        寻找语义边界位置
        
        返回需要在哪些位置断开（句子索引）
        """
        if len(sentences) < 2:
            return []

        # 获取所有句子的embedding
        embeddings = await self._get_embeddings(sentences)
        
        # 计算相邻句子的相似度
        breakpoints = []
        
        for i in range(len(sentences) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            
            # 如果相似度低于阈值，认为是语义边界
            if sim < self.breakpoint_threshold:
                breakpoints.append(i + 1)

        return breakpoints

    def _merge_with_size_limit(
        self, 
        sentences: List[str],
        breakpoints: List[int]
    ) -> List[str]:
        """根据边界合并句子，限制块大小"""
        if not breakpoints:
            return [" ".join(sentences)] if sentences else []

        # 添加首尾位置
        boundaries = [0] + breakpoints + [len(sentences)]
        
        chunks = []
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            chunk_sentences = sentences[start:end]
            
            # 如果块太小，尝试与下一个合并
            chunk_text = " ".join(chunk_sentences)
            
            if len(chunk_text) < self.min_chunk_size and i < len(boundaries) - 2:
                continue
            
            # 如果块太大，按固定大小分割
            if len(chunk_text) > self.max_chunk_size:
                # 递归分割
                sub_chunks = self._split_large_chunk(chunk_sentences)
                chunks.extend(sub_chunks)
            else:
                chunks.append(chunk_text)

        # 处理最后一个块
        if chunks:
            last_text = chunks[-1]
            if len(last_text) < self.min_chunk_size:
                # 合并到最后
                chunks = chunks[:-1]
                if chunks:
                    chunks[-1] = chunks[-1] + " " + last_text

        return [c for c in chunks if c.strip()]

    def _split_large_chunk(self, sentences: List[str]) -> List[str]:
        """将大块分割成小块"""
        chunks = []
        current = []
        size = 0

        for sent in sentences:
            sz = len(sent)
            if size + sz > self.max_chunk_size and current:
                chunks.append(" ".join(current))
                current = [sent]
                size = sz
            else:
                current.append(sent)
                size += sz

        if current:
            chunks.append(" ".join(current))

        return chunks

    async def chunk_document(
        self, 
        pages: List[Dict], 
        source_name: str = "doc"
    ) -> List[Dict[str, Any]]:
        """对文档进行语义分块"""
        # 先按固定方式预分块，减少计算量
        fixed_chunker = FixedChunker(
            chunk_size=self.max_chunk_size,
            chunk_overlap=50,
            min_chunk_size=self.min_chunk_size
        )

        all_sentences = []
        page_markers = []  # 记录每句话属于哪一页

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page", 0)
            
            # 按句子分割
            sentences = self.split_sentences(page_text)
            for sent in sentences:
                all_sentences.append(sent)
                page_markers.append(page_num)

        # 如果文本很少，直接用固定分块
        if len(all_sentences) < 5:
            return fixed_chunker.chunk_document(pages, source_name)

        # 查找语义边界
        try:
            breakpoints = await self._find_semantic_boundaries(all_sentences)
        except Exception:
            # 如果embedding失败，回退到固定分块
            return fixed_chunker.chunk_document(pages, source_name)

        # 合并成块
        chunk_texts = self._merge_with_size_limit(all_sentences, breakpoints)

        # 构建输出
        chunks = []
        for idx, chunk_text in enumerate(chunk_texts):
            chunks.append({
                "id": f"{source_name}_{idx}",
                "text": chunk_text,
                "source": source_name,
                "page": page_markers[min(idx, len(page_markers)-1)] if page_markers else 1,
                "char_count": len(chunk_text),
                "chunking_method": "semantic"
            })

        return chunks


def create_chunker(
    method: str = "fixed",
    **kwargs
) -> BaseChunker:
    """分块器工厂函数"""
    if method == "semantic":
        return SemanticChunker(**kwargs)
    return FixedChunker(**kwargs)


# 导出默认实例
text_chunker = FixedChunker()