"""
Document service — upload, list, get, delete documents with parsing & vectorisation.

Uploads are processed asynchronously: the file is saved and a Document row with
status="processing" is created immediately, then the parse → chunk → vectorise
pipeline runs in the background task worker. If the worker is not running
(e.g. in tests), processing falls back to synchronous execution.
"""

import logging
import os
import re
import uuid
from collections.abc import Awaitable, Callable

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.chunker import (
    create_chunker,
    deduplicate_chunks,
)
from app.core.document_parser import document_parser
from app.core.pgvector_store import PgVectorStore
from app.core.task_worker import enqueue
from app.db import Document, DocumentChunk, User
from app.exceptions import (
    AppError,
    ContentTooLargeError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from app.services import task_service

logger = logging.getLogger(__name__)


def _choose_chunker_method(total_text_len: int, sentence_count: int, filename: str = "") -> str:
    """Auto-select chunking strategy based on document characteristics."""
    # 幻灯片演示文稿（PPTX）：天然按页组织，固定分块保留单页边界最佳
    if filename.lower().endswith((".pptx", ".ppt")):
        return "fixed"

    # 长篇文档（>15k）且句子充分：层级分块兼具检索精度与大块上下文
    if total_text_len > 15_000 and sentence_count >= 15:
        return "hierarchical"

    # 中等长度单篇（3k ~ 15k）：语义分块计算量适中，边界切分高质量
    if 3_000 <= total_text_len <= 15_000 and sentence_count >= 5:
        return "semantic"

    # 短文或句子较少的情况：固定分块最稳定
    if sentence_count >= 10:
        return "hierarchical"

    return "fixed"


async def upload_document(
    db: AsyncSession,
    user: User,
    filename: str,
    content: bytes,
) -> dict:
    """Upload pipeline: validate → save file → create DB row → enqueue background processing.

    Returns dict with keys: id, filename, status, message, chunk_count.
    status is "processing" when handled by the background worker, or "ready"
    when processed synchronously (worker unavailable).
    """
    if not document_parser.is_supported(filename):
        supported = ", ".join(document_parser.supported_extensions)
        raise ValidationError(f"不支持的文件格式，仅支持: {supported}")

    file_size = len(content)
    if file_size > settings.max_file_size:
        raise ContentTooLargeError(f"文件过大，最大支持 {settings.max_file_size // 1024 // 1024}MB")
    if file_size == 0:
        raise ValidationError("文件内容为空")

    doc_id = str(uuid.uuid4())
    logger.info("Starting document upload: %s", filename)

    # Save file to disk
    uploads_dir = settings.upload_dir
    user_dir = os.path.join(uploads_dir, user.id)
    os.makedirs(user_dir, exist_ok=True)

    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    fp = os.path.join(user_dir, f"{doc_id}.{ext}")

    async with aiofiles.open(fp, "wb") as f:
        await f.write(content)
    logger.info("File saved, size: %d bytes", file_size)

    # Create the document row in "processing" state
    new_doc = Document(
        id=doc_id,
        user_id=user.id,
        filename=filename,
        file_path=fp,
        status="processing",
        chunk_count=0,
        file_size=file_size,
    )
    db.add(new_doc)
    try:
        await db.commit()
    except Exception:
        # 事务失败时清理磁盘上的孤儿文件
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
        raise

    # Create a tracking task and enqueue background processing
    task = await task_service.create_task(
        db, user.id, "document_process", {"doc_id": doc_id, "filename": filename}
    )
    try:
        await enqueue(
            task.id, user.id, "document_process", {"doc_id": doc_id, "filename": filename}
        )
        logger.info("Document %s queued for background processing", doc_id)
        return {
            "id": doc_id,
            "filename": filename,
            "status": "processing",
            "message": "文档已开始后台处理，请稍候查看",
            "chunk_count": 0,
        }
    except RuntimeError:
        # Worker not started (e.g. tests) — fall back to synchronous processing
        logger.warning("Task worker unavailable, processing document %s synchronously", doc_id)
        await task_service.update_task(db, task.id, user.id, status="running")
        try:
            chunk_count, method = await _do_process_document(db, user, doc_id)
            await task_service.update_task(
                db,
                task.id,
                user.id,
                status="completed",
                result={"doc_id": doc_id, "chunk_count": chunk_count},
            )
        except Exception as e:
            await task_service.update_task(db, task.id, user.id, status="failed", error=str(e))
            raise
        return {
            "id": doc_id,
            "filename": filename,
            "status": "ready",
            "message": f"上传成功，使用 {method} 分块策略",
            "chunk_count": chunk_count,
        }


async def _do_process_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
    progress_callback: Callable[[float, str], Awaitable[None]] | None = None,
) -> tuple[int, str]:
    """Parse → chunk → vectorise a saved document and update its DB row.

    Returns (chunk_count, chunking_method). Sets the document status to
    "ready" on success or "error" on failure.
    """
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    fp = doc.file_path
    method = "fixed"

    try:
        # Parse
        if progress_callback:
            await progress_callback(0.1, "正在解析文档...")
        try:
            logger.info("Starting document parsing...")
            pages = await document_parser.extract_pages(fp)
            logger.info("Parsing complete, %d pages extracted", len(pages))
            if not pages:
                raise ValidationError("无法从文档中提取文本内容")
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Failed to extract pages: %s", e)
            raise ExternalServiceError(f"文档解析失败: {str(e)}")

        if progress_callback:
            await progress_callback(0.3, f"文档解析完成，共提取 {len(pages)} 页内容")

        # Choose chunking strategy
        total_text_len = sum(len(p.get("text", "")) for p in pages)
        rough_sentences = sum(
            len(re.split(r"(?<=[.!?。！？;；])\s+", p.get("text", ""))) for p in pages
        )
        method = _choose_chunker_method(total_text_len, rough_sentences, doc.filename or "")
        logger.debug(
            "Auto-selected chunking method: %s (len=%d, sentences=%d)",
            method,
            total_text_len,
            rough_sentences,
        )

        # Chunk
        if progress_callback:
            await progress_callback(0.5, f"开始以 {method} 策略分块...")
        try:
            logger.info("Starting chunking with %s strategy...", method)
            chunker = create_chunker(method=method)
            chunks = await chunker.chunk_document(pages, doc_id)
            chunks = deduplicate_chunks(chunks, similarity_threshold=0.85)
            logger.info("Chunking complete, %d chunks created", len(chunks))
            if not chunks:
                raise ValidationError("文档内容不足，无法生成知识块")
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Failed to chunk document: %s", e)
            raise ExternalServiceError(f"文档分块失败: {str(e)}")

        # Build vector store (pgvector SQL-backed)
        if progress_callback:
            await progress_callback(0.7, f"分块完成（{len(chunks)} 块），正在计算向量并构建索引...")
        logger.info("Building vector store...")
        store = PgVectorStore(user_id=user.id)
        await store.add_chunks(chunks, doc_id, db=db)

        if progress_callback:
            await progress_callback(0.95, "正在完成数据库同步...")

        # Mark ready
        doc.status = "ready"
        doc.chunk_count = len(chunks)
        await db.commit()
        if progress_callback:
            await progress_callback(1.0, "处理完成")
        logger.info("Processing complete: %s (%d chunks)", doc_id, len(chunks))
        return len(chunks), method

    except Exception as e:
        await db.rollback()
        # Mark the document as failed
        doc.status = "error"
        await db.commit()
        if isinstance(e, AppError):
            raise
        logger.error("document processing: %s", e, exc_info=True)
        raise ExternalServiceError(str(e))


async def reprocess_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
) -> dict:
    """重新处理文档：清理旧 chunk，重置状态为 processing，并重新派发异步任务。"""
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise NotFoundError("原始文件不存在，请重新上传文件")

    # 清理该文档现存的 chunk 记录（防止残留脏数据）
    await db.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    doc.status = "processing"
    doc.chunk_count = 0
    await db.commit()

    # 创建新的异步处理任务并入队
    task = await task_service.create_task(
        db, user.id, "document_process", {"doc_id": doc_id, "filename": doc.filename}
    )
    try:
        await enqueue(
            task.id, user.id, "document_process", {"doc_id": doc_id, "filename": doc.filename}
        )
        logger.info("Document %s re-queued for background processing", doc_id)
        return {
            "id": doc_id,
            "filename": doc.filename,
            "status": "processing",
            "message": "文档已开始重新处理，请稍候查看",
            "chunk_count": 0,
        }
    except RuntimeError:
        # Worker 未运行（测试或离线模式），同步执行回退
        logger.warning("Task worker unavailable, re-processing document %s synchronously", doc_id)
        await task_service.update_task(db, task.id, user.id, status="running")
        try:
            chunk_count, method = await _do_process_document(db, user, doc_id)
            await task_service.update_task(
                db,
                task.id,
                user.id,
                status="completed",
                result={"doc_id": doc_id, "chunk_count": chunk_count},
            )
        except Exception as e:
            await task_service.update_task(db, task.id, user.id, status="failed", error=str(e))
            raise
        return {
            "id": doc_id,
            "filename": doc.filename,
            "status": "ready",
            "message": f"重新处理成功，使用 {method} 分块策略",
            "chunk_count": chunk_count,
        }


async def list_documents(
    db: AsyncSession,
    user: User,
    limit: int | None = None,
    offset: int = 0,
) -> list[Document]:
    """Return documents owned by user, newest first.

    limit/offset 为可选分页参数：缺省返回全部（兼容既有前端）。
    """
    query = (
        select(Document)
        .where(Document.user_id == user.id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
    )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
) -> dict:
    """Get a single document with its chunks from the database."""
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(Document).where(
            Document.id == doc_id,
            Document.user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    # Fetch chunks from PostgreSQL (replaces file-based vector store load)
    chunks_result = await db.execute(
        sa_select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = [
        {
            "text": c.content,
            "chunk_metadata": c.chunk_metadata or {},
        }
        for c in chunks_result.scalars().all()
    ]

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "file_size": doc.file_size,
        "created_at": str(doc.created_at),
        "chunks": chunks,
    }


async def delete_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
) -> None:
    """软删除文档（进回收站，可 restore）：保留文件与索引，仅打标记。

    Vector store 数据在 DB 中，不需要额外的 evict。
    """
    from datetime import UTC, datetime

    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == user.id,
            Document.deleted_at.is_(None),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    doc.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()


async def restore_document(db: AsyncSession, user: User, doc_id: str) -> Document:
    """从回收站恢复软删除的文档（文件与索引未动，恢复即用）。"""
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == user.id,
            Document.deleted_at.is_not(None),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("回收站中没有该文档")
    doc.deleted_at = None
    await db.commit()
    return doc


async def purge_deleted_documents(
    db: AsyncSession,
    user: User,
    older_than_days: int = 30,
) -> int:
    """物理清除回收站中超期的文档（DB行+chunk+文件）。返回清除数量。

    仅供运维脚本/显式调用，不接入 HTTP。
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete as sa_delete
    from sqlalchemy import select as sa_select

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=older_than_days)
    result = await db.execute(
        sa_select(Document).where(
            Document.user_id == user.id,
            Document.deleted_at.is_not(None),
            Document.deleted_at < cutoff,
        )
    )
    stale = list(result.scalars().all())

    for doc in stale:
        # Delete associated chunks (cascading from documents FK is also fine,
        # but explicit DELETE is safer for bulk purge)
        await db.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        # Remove file
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        await db.delete(doc)

    if stale:
        await db.commit()
        logger.info("Purged %d soft-deleted documents (user=%s)", len(stale), user.id)
    return len(stale)
