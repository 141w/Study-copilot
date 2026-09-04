"""
Document Bundle — 多文档打包为 LLM 可消费的文本。

参考 OpenMAIC 的 `lib/document/bundle.ts`，做 Python 移植：
- CJK 字符预算控制（中文环境下 1 字符 ≈ 1 token）
- 多文档合并（最多 5 篇，150MB 上限）
- 按章节分隔 + 来源标记

仅用于 RAG 引擎的多文档上下文增强（ask / discuss 模式）。
"""

from dataclasses import dataclass, field
from typing import Any

from app.db import Document, DocumentChunk


@dataclass
class BundleResult:
    """多文档打包结果。"""
    text: str
    source_names: list[str]
    total_chars: int = 0
    truncated: bool = False


# ── 常量 ─────────────────────────────────────────────────────────────────────
MAX_FILES = 5
MAX_BYTES = 150 * 1024 * 1024          # 150 MB
MAX_TEXT_CHARS = 1_000_000             # CJK 字符预算
SECTION_SEP = "\n\n---\n\n"


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    """按 CJK 字符边界截断，不在单词/汉字中间切断。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    sliced = text[:max_chars]
    # 回退到最近的空白/换行边界
    for i in range(len(sliced) - 1, max(0, len(sliced) - 200), -1):
        if sliced[i] in ('\n', '。', '！', '？', '.', '!', '?', ' ', '，'):
            return sliced[:i + 1]
    return sliced


async def build_bundle(
    documents: list[tuple[str, str]],
) -> BundleResult:
    """将多个文档打包为单个文本。

    参数
    ----
    documents : list[tuple[str, str]]
        [(filename, content_text), ...]

    返回
    ----
    BundleResult  with .text / .source_names / .total_chars / .truncated
    """
    source_names: list[str] = []
    parts: list[str] = []
    total_chars = 0
    truncated = False

    for idx, (filename, content) in enumerate(documents[:MAX_FILES]):
        name = filename or f"文档{idx + 1}"
        source_names.append(name)

        header = f"【来源 {idx + 1}】{name}"
        body = content.strip()

        # 检查单文档是否超过总预算（给标题留存 100 字符余量）
        if total_chars + len(header) + 2 + len(body) > MAX_TEXT_CHARS:
            remaining = MAX_TEXT_CHARS - total_chars - len(header) - 2
            if remaining > 200:
                body = _truncate_at_boundary(body, remaining)
                parts.append(f"{header}\n{body}")
                total_chars += len(header) + 1 + len(body)
            truncated = True
            break

        parts.append(f"{header}\n{body}")
        total_chars += len(header) + 1 + len(body)

    return BundleResult(
        text=SECTION_SEP.join(parts),
        source_names=source_names,
        total_chars=total_chars,
        truncated=truncated,
    )


async def build_bundle_from_doc_ids(
    db: Any,
    doc_ids: list[str],
) -> BundleResult:
    """从数据库 doc_id 列表构建文档包。"""
    if not doc_ids:
        return BundleResult(text="", source_names=[])

    result = await db.execute(
        DocumentChunk.__table__.select()
        .where(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    rows = result.all()

    # 按 document_id 分组
    doc_chunks: dict[str, list[str]] = {}
    for row in rows:
        doc_id = row.document_id
        doc_chunks.setdefault(doc_id, []).append(row.content)

    # 获取文件名
    doc_result = await db.execute(
        Document.__table__.select().where(Document.id.in_(doc_ids))
    )
    doc_names = {row.id: row.filename for row in doc_result.all()}

    documents = []
    for doc_id in doc_ids:
        if doc_id in doc_chunks:
            filename = doc_names.get(doc_id, doc_id)
            content = "\n\n".join(doc_chunks[doc_id])
            documents.append((filename, content))

    return await build_bundle(documents)
