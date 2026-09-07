"""
Document bundle — 多文档打包与文本预算分配算法。

基于两阶段公平预算控制：
  1. 每篇文档保证基础预算（默认 1500 字符）
  2. 剩余预算按各文档需求比例分配
  3. 安全标点截断（句子/换行边界，避免切断中文字词）

仅用于 AI 课堂引擎的多文档上下文增强（ask / discuss 模式）。
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
MAX_BYTES = 150 * 1024 * 1024  # 150 MB
MAX_TEXT_CHARS = 1_000_000  # CJK 字符预算
BASE_BUDGET_PER_DOCUMENT = 1500  # 每篇文档保底预算
RESERVED_BUDGET_RATIO = 0.4  # 保底预算总额占总上限比例
SECTION_SEP = "\n\n---\n\n"


def allocate_document_text_budgets(lengths: list[int], max_chars: int) -> list[int]:
    """文档文本公平预算分配算法：

    两阶段字符预算分配：
    1. 为每篇文档预留保底预算（最多 1500 字符或总预算的 40% / N），确保多文档时不被长文档完全挤占
    2. 剩余预算按各文档未满足需求的比例公平分配
    """
    if not lengths or max_chars <= 0:
        return [0] * len(lengths)

    num_docs = len(lengths)
    reserved = min(
        num_docs * BASE_BUDGET_PER_DOCUMENT,
        int(max_chars * RESERVED_BUDGET_RATIO),
    )
    base_per_doc = reserved // num_docs
    budgets = [min(l, base_per_doc) for l in lengths]
    remaining_budget = max_chars - sum(budgets)

    # 记录尚未完全满足的文档
    unmet = [
        {"index": idx, "remaining": max(0, lengths[idx] - budgets[idx])}
        for idx in range(num_docs)
        if lengths[idx] > budgets[idx]
    ]

    while remaining_budget > 0 and unmet:
        total_remaining = sum(e["remaining"] for e in unmet)
        if total_remaining == 0:
            break

        distributed = 0
        for entry in list(unmet):
            if remaining_budget == 0:
                break
            share = (remaining_budget * entry["remaining"]) // total_remaining
            allocation = min(entry["remaining"], max(share, 1), remaining_budget)
            budgets[entry["index"]] += allocation
            entry["remaining"] -= allocation
            remaining_budget -= allocation
            distributed += allocation

        if distributed == 0:
            target = next((e for e in unmet if e["remaining"] > 0), None)
            if not target:
                break
            budgets[target["index"]] += 1
            target["remaining"] -= 1
            remaining_budget -= 1

        unmet = [e for e in unmet if e["remaining"] > 0]

    return budgets


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    """按 CJK 字符边界截断，不在单词/汉字中间切断。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    sliced = text[:max_chars]
    # 回退到最近的空白/标点边界
    for i in range(len(sliced) - 1, max(0, len(sliced) - 200), -1):
        if sliced[i] in ("\n", "。", "！", "？", ".", "!", "?", " ", "，", "、", "；", ";"):
            return sliced[: i + 1]
    return sliced


async def build_bundle(
    documents: list[tuple[str, str]],
) -> BundleResult:
    """将多个文档打包为单个文本。

    采用两阶段公平预算控制：
    - 保底预算防止长文档挤占短文档
    - 剩余预算按比例分配
    - 边界安全截断

    参数
    ----
    documents : list[tuple[str, str]]
        [(filename, content_text), ...]

    返回
    ----
    BundleResult  with .text / .source_names / .total_chars / .truncated
    """
    source_names: list[str] = []
    headers: list[str] = []
    bodies: list[str] = []

    for idx, (filename, content) in enumerate(documents[:MAX_FILES]):
        name = filename or f"文档{idx + 1}"
        source_names.append(name)
        headers.append(f"【来源 {idx + 1}】{name}")
        bodies.append(content.strip())

    if not bodies:
        return BundleResult(text="", source_names=[], total_chars=0, truncated=False)

    # 头部字符消耗（每个头部后紧跟一个换行）
    header_chars = sum(len(h) + 1 for h in headers)
    body_budget = max(0, MAX_TEXT_CHARS - header_chars)
    raw_lengths = [len(b) for b in bodies]

    total_raw_with_headers = header_chars + sum(raw_lengths)
    truncated = total_raw_with_headers > MAX_TEXT_CHARS

    if truncated:
        allocated = allocate_document_text_budgets(raw_lengths, body_budget)
        truncated_bodies = [
            _truncate_at_boundary(body, limit) if len(body) > limit else body
            for body, limit in zip(bodies, allocated)
        ]
    else:
        truncated_bodies = bodies

    parts: list[str] = []
    total_chars = 0
    for header, body in zip(headers, truncated_bodies):
        if body:
            parts.append(f"{header}\n{body}")
            total_chars += len(header) + 1 + len(body)
        else:
            parts.append(header)
            total_chars += len(header)

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
    doc_result = await db.execute(Document.__table__.select().where(Document.id.in_(doc_ids)))
    doc_names = {row.id: row.filename for row in doc_result.all()}

    documents = []
    for doc_id in doc_ids:
        if doc_id in doc_chunks:
            filename = doc_names.get(doc_id, doc_id)
            content = "\n\n".join(doc_chunks[doc_id])
            documents.append((filename, content))

    return await build_bundle(documents)
