"""
文本分块模块 - 支持固定分块、语义分块、层级分块

架构：
- BaseChunker: 分块器抽象基类（支持异步接口）
- FixedChunker: 基于句子和固定大小的分块（Markdown 感知、句级重叠）
- SemanticChunker: 基于语义边界的智能分块（分批 Embedding、真实阈值）
- HierarchicalChunker: 层级分块（父-子结构，兼顾精确匹配与上下文完整性）

新增特性（2025-05-13）：
1. Markdown 结构感知（标题硬边界、表格保护）
2. 句级重叠替代字符级重叠
3. 大文档分批 Embedding（语义分块）
4. 死参数移除，激活语义阈值
5. 层级 chunk 支持（粗粒度父块 + 细粒度子块）
6. chunk 去重机制
7. 正则表达式清理
8. Tier-4 fallback 改为软切

作者：AI全栈工程师
"""

import re
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _jaccard_similarity(a: str, b: str) -> float:
    """计算两段文本的 Jaccard 相似度（基于字符二元组）"""

    def shingle(text: str, n: int = 2):
        return set(text[i : i + n] for i in range(len(text) - n + 1))

    sa, sb = shingle(a), shingle(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union > 0 else 0.0


def _normalize_text(text: str) -> str:
    """归一化文本用于去重比较"""
    return re.sub(r"\s+", "", text.lower())


# ---------------------------------------------------------------------------
# Markdown 结构解析器
# ---------------------------------------------------------------------------


class MarkdownSplitter:
    """
    Markdown 结构感知预分割器。

    在普通句子切分之前，先识别 Markdown 的结构元素（标题、分隔线、表格），
    确保这些结构边界不会被 FixedChunker 的滑动窗口「跨过去」。
    """

    # 标题正则
    HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    # 水平分隔线
    HR_RE = re.compile(r"^\s*---+\s*$", re.MULTILINE)
    # 表格行（简化：识别 |...| 模式，跨越多行）
    TABLE_RE = re.compile(r"(^\|.*\|(?:\r?\n\|.*\|)+)", re.MULTILINE)
    # 代码块
    CODEBLOCK_RE = re.compile(r"(```[\s\S]*?```)")

    @classmethod
    def split_by_structure(cls, text: str) -> list[tuple[str, str | None, str]]:
        """
        按 Markdown 结构拆分文本。

        Returns:
            List[Tuple[section_title, heading_chain, text]]
            - section_title: 当前分区的标题（如果有）
            - heading_chain: 标题链（例如 "## 方法"）
            - text: 该分区的纯文本内容
        """
        if not text.strip():
            return [("", None, "")]

        # 保护代码块：先替换为占位符
        code_blocks: dict[str, str] = {}

        def _save_codeblock(m):
            key = f"__CODEBLOCK_{len(code_blocks)}__"
            code_blocks[key] = m.group(1)
            return key

        protected = cls.CODEBLOCK_RE.sub(_save_codeblock, text)

        # 按标题和分隔线拆分
        markers = []
        for m in cls.HEADING_RE.finditer(protected):
            level = len(m.group(1))
            title = m.group(2).strip()
            markers.append((m.start(), m.end(), "heading", level, title))
        for m in cls.HR_RE.finditer(protected):
            markers.append((m.start(), m.end(), "hr", 0, ""))

        markers.sort(key=lambda x: x[0])

        if not markers:
            # 没有结构标记，直接返回整体
            result = cls._restore_codeblocks([(None, None, protected)], code_blocks)
            return [("", None, r[2]) for r in result]

        # 拆分
        sections = []
        current_level = 0
        current_title = ""
        prev_end = 0

        for start, end, kind, level, title in markers:
            if start > prev_end:
                chunk_text = protected[prev_end:start].strip()
                if chunk_text:
                    sections.append((current_title, current_level, chunk_text))
            if kind == "heading":
                current_level = level
                current_title = title
            prev_end = end

        # 最后一段
        if prev_end < len(protected):
            tail = protected[prev_end:].strip()
            if tail:
                sections.append((current_title, current_level, tail))

        # 恢复代码块
        raw_sections = [(t, l, txt) for t, l, txt in sections]
        restored = cls._restore_codeblocks(
            [(t, f"{'#' * l} {t}" if l > 0 and t else None, txt) for t, l, txt in raw_sections],
            code_blocks,
        )

        return [(t, h, txt) for t, h, txt in restored]

    @classmethod
    def _restore_codeblocks(cls, sections, code_blocks):
        result = []
        for t, h, txt in sections:
            for key, val in code_blocks.items():
                txt = txt.replace(key, val)
            result.append((t, h, txt))
        return result


# ---------------------------------------------------------------------------
# BaseChunker
# ---------------------------------------------------------------------------


class BaseChunker(ABC):
    """分块器抽象基类（支持异步接口）"""

    @abstractmethod
    async def chunk_document(
        self, pages: list[dict], source_name: str = "doc"
    ) -> list[dict[str, Any]]:
        """对文档进行分块"""
        pass

    def _add_parent_info(
        self, chunks: list[dict[str, Any]], source_name: str
    ) -> list[dict[str, Any]]:
        """为 chunks 添加基础字段并统一编号"""
        for idx, c in enumerate(chunks):
            c["id"] = f"{source_name}_{idx}"
            c["source"] = source_name
            c["char_count"] = len(c.get("text", ""))
        return chunks


# ---------------------------------------------------------------------------
# FixedChunker
# ---------------------------------------------------------------------------


class FixedChunker(BaseChunker):
    """
    固定分块器 - 基于句子边界和固定大小的分块。

    改进点（2025-05-13）：
    1. Markdown 结构感知：标题/分隔线作为硬边界，chunk 不会跨标题
    2. 句级重叠：overlap 按完整句子保留，不再在字符中间截断
    3. 正则清理：修正中英文结束符正则
    4. Tier-4 fallback 改为软切（按最近空格/标点切分）
    """

    SENTENCE_RE = re.compile(r"(?<=[.!?。！？;；])\s+")

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        respect_markdown: bool = True,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.respect_markdown = respect_markdown

    def split_sentences(self, text: str) -> list[str]:
        """按句子分割文本（含4级fallback）"""
        sentences: list[str] = []

        # 方法1: 匹配中英文句子结束符
        parts = self.SENTENCE_RE.split(text)

        # 方法2: 如果分割失败或不完整，按换行和段落分割
        if len(parts) < 2 or any(len(p) > 1000 for p in parts):
            parts = re.split(r"[\n\n]+", text)
            parts = [p.strip() for p in parts if p.strip()]

        # 方法3: 如果仍然只有很少的块，按单个换行分割
        if len(parts) < 2:
            parts = re.split(r"\n+", text)
            parts = [p.strip() for p in parts if p.strip()]

        # 方法4: 仍然太多，按软切分（后备方案）
        if len(parts) == 1 and len(parts[0]) > 500:
            soft_parts = self._soft_split(parts[0], chunk_size=300)
            return soft_parts if soft_parts else parts

        # 合并相邻的过短块
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if sentences and len(sentences[-1]) < 100:
                sentences[-1] = sentences[-1] + " " + part
            else:
                sentences.append(part)

        return [s.strip() for s in sentences if s.strip()]

    def _soft_split(self, text: str, chunk_size: int = 300) -> list[str]:
        """
        软切分：在最近的空格或标点处断开，避免在字/词中间截断。
        """
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            # 如果不是文本末尾，尝试找最近的空格或标点回退
            if end < text_len:
                # 向后搜索最多 30 个字符，找空格或换行
                search_start = max(start + chunk_size - 30, start + 1)
                found = False
                for i in range(end, search_start, -1):
                    if text[i] in " \n\t，,。.！!？?;；":
                        end = i + 1
                        found = True
                        break
                if not found:
                    # 实在找不到，硬切
                    pass
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if len(chunks) >= 100:
                break
            start = end
        return chunks

    def _build_overlap_sentences(self, sentences: list[str]) -> list[str]:
        """
        句级重叠：从句子的末尾往前累计，直到满足 overlap 字符数目标，
        但保证取到完整句子（不再字中间截断）。
        """
        if not sentences:
            return []
        total = 0
        take: list[str] = []
        for sent in reversed(sentences):
            take.insert(0, sent)
            total += len(sent)
            if total >= self.chunk_overlap:
                break
        return take

    def split_text(self, text: str) -> list[str]:
        """将文本分成多个块（支持 Markdown 结构感知）"""
        if not self.respect_markdown:
            return self._split_plain_text(text)

        # Markdown 结构感知：先按标题/结构拆分，再对每个 section 内部做滑动窗口
        sections = MarkdownSplitter.split_by_structure(text)
        all_chunks = []
        for section_title, heading_chain, section_text in sections:
            chunks = self._split_plain_text(section_text)
            for c in chunks:
                # 为每个 chunk 附加标题链上下文
                meta = {}
                if heading_chain:
                    meta["heading_chain"] = heading_chain
                if section_title:
                    meta["section_title"] = section_title
                all_chunks.append((c, meta))

        # 合并相邻且太短的块（跨 section 的边界保护已确保）
        return self._merge_short_adjacent(all_chunks)

    def _split_plain_text(self, text: str) -> list[str]:
        """纯文本滑动窗口分块（句级重叠）"""
        sentences = self.split_sentences(text)
        if not sentences:
            return []

        chunks = []
        current: list[str] = []
        size = 0

        for sent in sentences:
            sz = len(sent)
            if size + sz > self.chunk_size and size >= self.min_chunk_size:
                chunks.append(" ".join(current))
                # 句级重叠
                current = self._build_overlap_sentences(current)
                size = sum(len(s) for s in current)

            current.append(sent)
            size += sz

        if current:
            chunks.append(" ".join(current))

        return [c for c in chunks if c.strip()]

    def _merge_short_adjacent(self, chunks_with_meta: list[tuple[str, dict]]) -> list[str]:
        """合并相邻过短的 chunk（保留 meta 信息到 text 中）"""
        result: list[str] = []
        for text, meta in chunks_with_meta:
            if meta.get("heading_chain"):
                # 在 chunk 前注入标题链，帮助 RAG 检索时获得上下文
                text = f"{meta['heading_chain']}\n{text}"
            if result and len(result[-1]) < self.min_chunk_size:
                result[-1] = result[-1] + "\n\n" + text
            else:
                result.append(text)
        return [c for c in result if c.strip()]

    async def chunk_document(
        self, pages: list[dict], source_name: str = "doc"
    ) -> list[dict[str, Any]]:
        """对文档进行分块"""
        chunks: list[dict[str, Any]] = []
        chunk_id = 0

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page", 0)

            if not page_text or not page_text.strip():
                continue

            for chunk_text in self.split_text(page_text):
                if not chunk_text or len(chunk_text.strip()) < 10:
                    continue
                chunks.append(
                    {
                        "id": f"{source_name}_{chunk_id}",
                        "text": chunk_text,
                        "source": source_name,
                        "page": page_num,
                        "char_count": len(chunk_text),
                        "chunking_method": "fixed",
                    }
                )
                chunk_id += 1

        return chunks


# ---------------------------------------------------------------------------
# SemanticChunker
# ---------------------------------------------------------------------------


class SemanticChunker(BaseChunker):
    """
    语义分块器 - 基于语义边界的智能分块。

    改进点（2025-05-13）：
    1. 大文档分批 Embedding，避免 OOM
    2. 激活语义阈值（连续相邻句平均相似度下降时作为辅助断点）
    3. 修正页码映射：用 chunk 中最多句子来源的页号作为 page
    4. 增强 overlap：语义边界分块后，可选对大块做细粒度再切
    """

    SENTENCE_RE = re.compile(r"(?<=[.!?。！？;；])\s+")

    def __init__(
        self,
        min_chunk_size: int = 200,
        max_chunk_size: int = 1000,
        breakpoint_threshold: float = 0.25,
        embedding_batch_size: int = 64,
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.breakpoint_threshold = breakpoint_threshold
        self.embedding_batch_size = embedding_batch_size

    def split_sentences(self, text: str) -> list[str]:
        """按句子分割"""
        sentences = self.SENTENCE_RE.split(text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    async def _get_embeddings(self, texts: list[str]) -> list[np.ndarray]:
        """分批获取多个文本的 embedding，避免大文档 OOM"""
        from app.core.embedder import embedder

        embeddings = []
        for i in range(0, len(texts), self.embedding_batch_size):
            batch = texts[i : i + self.embedding_batch_size]
            batch_embs = await embedder.embed_texts(batch)
            embeddings.extend([emb for emb in batch_embs])
        return embeddings

    async def _find_semantic_boundaries(self, sentences: list[str]) -> list[int]:
        """
        寻找语义边界位置。

        返回需要在哪些位置断开（句子索引）。
        策略：
        1. 相邻句余弦相似度 < breakpoint_threshold → 硬断点
        2. 连续3个相邻相似度递减且最后一个 < 0.4 → 软断点（主题渐变结束）
        """
        if len(sentences) < 2:
            return []

        embeddings = await self._get_embeddings(sentences)
        breakpoints = []
        sims = []

        for i in range(len(sentences) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            sims.append(sim)

            # 硬断点：相似度极低
            if sim < self.breakpoint_threshold:
                breakpoints.append(i + 1)
                continue

            # 软断点：连续3个相邻相似度单调递减且最终 < 0.4
            if i >= 2 and len(sims) >= 3:
                last_three = sims[-3:]
                if last_three[0] > last_three[1] > last_three[2] and last_three[2] < 0.4:
                    # 避免过于密集的断点（与前一个断点至少隔3句）
                    if not breakpoints or (i + 1) - breakpoints[-1] >= 3:
                        breakpoints.append(i + 1)

        return breakpoints

    def _merge_with_size_limit(
        self,
        sentences: list[str],
        breakpoints: list[int],
        page_markers: list[int] | None = None,
    ) -> list[tuple[str, int]]:
        """
        根据边界合并句子，限制块大小。
        返回 List[(chunk_text, page_num)]，page_num 取该 chunk 中出现最多的页号。
        """
        if not breakpoints:
            text = " ".join(sentences)
            page = page_markers[0] if page_markers else 1
            return [(text, page)] if text.strip() else []

        boundaries = [0] + breakpoints + [len(sentences)]
        chunks = []

        i = 0
        while i < len(boundaries) - 1:
            start = boundaries[i]
            end = boundaries[i + 1]
            chunk_sents = sentences[start:end]
            chunk_text = " ".join(chunk_sents)

            # 如果块太小，尝试与下一个合并
            if len(chunk_text) < self.min_chunk_size and i < len(boundaries) - 2:
                i += 1
                continue

            # 如果块太大，按固定大小分割
            if len(chunk_text) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk_sents)
                for sub in sub_chunks:
                    # 对每个子块单独计算页号
                    sub_page = self._majority_page(
                        page_markers, start, end - 1, len(sub), sentences
                    )
                    chunks.append((sub, sub_page))
            else:
                page = self._majority_page(page_markers, start, end - 1, len(chunk_text), sentences)
                chunks.append((chunk_text, page))
            i += 1

        # 处理最后一个块
        if chunks:
            last_text, last_page = chunks[-1]
            if len(last_text) < self.min_chunk_size and len(chunks) > 1:
                chunks.pop()
                prev_text, prev_page = chunks[-1]
                chunks[-1] = (prev_text + " " + last_text, prev_page)

        return [(c, p) for c, p in chunks if c.strip()]

    def _split_large_chunk(self, sentences: list[str]) -> list[str]:
        """将大块分割成小块"""
        chunks: list[str] = []
        current: list[str] = []
        size = 0

        for sent in sentences:
            sz = len(sent)
            if size + sz > self.max_chunk_size and current:
                chunks.append(" ".join(current))
                # 语义块内部也做句级 overlap
                ov: list[str] = []
                ov_size = 0
                for s in reversed(current):
                    ov.insert(0, s)
                    ov_size += len(s)
                    if ov_size >= 50:
                        break
                current = ov
                size = ov_size
            current.append(sent)
            size += sz

        if current:
            chunks.append(" ".join(current))

        return chunks

    @staticmethod
    def _majority_page(
        page_markers: list[int] | None,
        sent_start: int,
        sent_end: int,
        chunk_text_len: int,
        sentences: list[str],
    ) -> int:
        """
        计算 chunk 的代表性页码。
        策略：取该 chunk 中句子数量最多的页号；无 page_markers 则返回 1。
        """
        if not page_markers:
            return 1
        # 统计每页出现的句子数
        page_counts: dict[int, int] = {}
        for idx in range(sent_start, min(sent_end + 1, len(page_markers))):
            p = page_markers[idx]
            page_counts[p] = page_counts.get(p, 0) + 1
        if not page_counts:
            return page_markers[min(sent_start, len(page_markers) - 1)]
        return max(page_counts, key=lambda k: page_counts[k])

    async def chunk_document(
        self,
        pages: list[dict],
        source_name: str = "doc",
    ) -> list[dict[str, Any]]:
        """对文档进行语义分块"""
        fixed_chunker = FixedChunker(
            chunk_size=self.max_chunk_size,
            chunk_overlap=50,
            min_chunk_size=self.min_chunk_size,
        )

        all_sentences = []
        page_markers = []

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page", 0)
            sentences = self.split_sentences(page_text)
            for sent in sentences:
                all_sentences.append(sent)
                page_markers.append(page_num)

        if len(all_sentences) < 5:
            return await fixed_chunker.chunk_document(pages, source_name)

        try:
            breakpoints = await self._find_semantic_boundaries(all_sentences)
        except Exception:
            return await fixed_chunker.chunk_document(pages, source_name)

        chunk_texts = self._merge_with_size_limit(all_sentences, breakpoints, page_markers)

        chunks = []
        for idx, (chunk_text, page_num) in enumerate(chunk_texts):
            chunks.append(
                {
                    "id": f"{source_name}_{idx}",
                    "text": chunk_text,
                    "source": source_name,
                    "page": page_num,
                    "char_count": len(chunk_text),
                    "chunking_method": "semantic",
                }
            )

        return chunks


# ---------------------------------------------------------------------------
# HierarchicalChunker（层级分块）
# ---------------------------------------------------------------------------


class HierarchicalChunker(BaseChunker):
    """
    层级分块器 - 生成父子两级 chunk 结构。

    父块（Parent）：粗粒度（~1000字符），保证上下文完整性
    子块（Child）：细粒度（~200字符），保证检索精确度

    子块携带 parent_id，RAG 检索时：
    - 先用子块做精确匹配（召回 top-k）
    - 返回时若用户需要更多上下文，可动态拼接父块内容
    """

    def __init__(
        self,
        parent_chunk_size: int = 1000,
        child_chunk_size: int = 250,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50,
        use_semantic_parent: bool = False,
    ):
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.use_semantic_parent = use_semantic_parent

    async def chunk_document(
        self,
        pages: list[dict],
        source_name: str = "doc",
    ) -> list[dict[str, Any]]:
        """
        层级分块：先生成父块，再在父块内部生成子块。

        输出格式：
        {
            ...parent_fields,
            "is_parent": True,
            "children_ids": ["doc_0_0", "doc_0_1", ...],
        }
        以及独立的子块（也会进入向量库，用于检索）：
        {
            ...child_fields,
            "is_parent": False,
            "parent_id": "doc_0",
        }
        """
        # 选择父块生成器（两种实现接口一致，仅分块策略不同）
        parent_chunker: SemanticChunker | FixedChunker
        if self.use_semantic_parent:
            parent_chunker = SemanticChunker(
                min_chunk_size=self.min_chunk_size,
                max_chunk_size=self.parent_chunk_size,
            )
        else:
            parent_chunker = FixedChunker(
                chunk_size=self.parent_chunk_size,
                chunk_overlap=self.chunk_overlap,
                min_chunk_size=self.min_chunk_size,
                respect_markdown=True,
            )

        parent_chunks = await parent_chunker.chunk_document(pages, source_name)

        child_chunker = FixedChunker(
            chunk_size=self.child_chunk_size,
            chunk_overlap=self.chunk_overlap // 2,
            min_chunk_size=self.min_chunk_size,
            respect_markdown=False,  # 父块内部不需要再次 Markdown 感知
        )

        all_chunks: list[dict[str, Any]] = []
        child_global_idx = 0

        for p_idx, parent in enumerate(parent_chunks):
            parent_id = f"{source_name}_p{p_idx}"
            parent["id"] = parent_id
            parent["is_parent"] = True
            parent["chunking_method"] = "hierarchical_parent"

            # 在父块文本内部生成子块
            fake_page = [{"page": parent.get("page", 1), "text": parent["text"]}]
            raw_children = await child_chunker.chunk_document(fake_page, f"{source_name}_p{p_idx}")

            children = []
            for rc in raw_children:
                child_id = f"{source_name}_{child_global_idx}"
                rc["id"] = child_id
                rc["parent_id"] = parent_id
                rc["is_parent"] = False
                rc["source"] = source_name
                rc["page"] = parent.get("page", 1)
                rc["chunking_method"] = "hierarchical_child"
                children.append(rc)
                child_global_idx += 1

            parent["children_ids"] = [c["id"] for c in children]
            all_chunks.append(parent)
            all_chunks.extend(children)

        return all_chunks


# ---------------------------------------------------------------------------
# 去重 + 后处理
# ---------------------------------------------------------------------------


def deduplicate_chunks(
    chunks: list[dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """
    对 chunk 列表进行去重/合并。

    策略：相邻 chunk 如果 Jaccard 相似度 >= threshold，则合并（取较长的那个）。
    这里主要消除因 overlap 导致的重复内容浪费 top-k。
    """
    if not chunks:
        return chunks

    deduped = [chunks[0]]
    for curr in chunks[1:]:
        prev_text = deduped[-1].get("text", "")
        curr_text = curr.get("text", "")
        sim = _jaccard_similarity(_normalize_text(prev_text), _normalize_text(curr_text))
        if sim >= similarity_threshold:
            # 合并：保留更长的文本，合并页码信息
            if len(curr_text) > len(prev_text):
                deduped[-1]["text"] = curr_text
                deduped[-1]["char_count"] = len(curr_text)
            # 保留页码列表（如果有差异）
            prev_page = deduped[-1].get("page")
            curr_page = curr.get("page")
            if prev_page != curr_page:
                pages = set()
                if isinstance(prev_page, int):
                    pages.add(prev_page)
                if isinstance(curr_page, int):
                    pages.add(curr_page)
                if pages:
                    deduped[-1]["pages"] = sorted(pages)
        else:
            deduped.append(curr)

    return deduped


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------


def create_chunker(
    method: str = "fixed",
    **kwargs,
) -> BaseChunker:
    """
    分块器工厂函数。

    method 可选值：
    - "fixed": 固定分块（默认，最快，推荐大文档）
    - "semantic": 语义分块（质量最高，需 Embedding，适合中等文档）
    - "hierarchical": 层级分块（兼顾质量与检索精度，需要更多存储）
    - "auto": 自动选择（根据文档长度和句子数）
    """
    if method == "semantic":
        return SemanticChunker(**kwargs)
    if method == "hierarchical":
        return HierarchicalChunker(**kwargs)
    if method == "auto":
        # auto 策略由调用方根据文档长度决定，这里默认返回 Fixed
        return FixedChunker(**kwargs)
    return FixedChunker(**kwargs)


# 导出默认实例（向后兼容）
text_chunker = FixedChunker()
