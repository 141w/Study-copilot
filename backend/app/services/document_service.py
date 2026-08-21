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

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.chunker import (
    create_chunker,
    deduplicate_chunks,
)
from app.core.document_parser import document_parser
from app.core.task_worker import enqueue
from app.core.vector_store import DocumentVectorStore
from app.db import Document, User
from app.exceptions import (
    AppError,
    ContentTooLargeError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from app.services import task_service

logger = logging.getLogger(__name__)


def _choose_chunker_method(total_text_len: int, sentence_count: int) -> str:
    """Auto-select chunking strategy based on document characteristics."""
    if total_text_len > 100_000:
        return "fixed"
    if total_text_len > 20_000:
        return "semantic"
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
    await db.commit()

    # Create a tracking task and enqueue background processing
    task = await task_service.create_task(
        db, user.id, "document_process", {"doc_id": doc_id, "filename": filename}
    )
    try:
        await enqueue(task.id, user.id, "document_process", {"doc_id": doc_id})
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
                db, task.id, user.id, status="completed",
                result={"doc_id": doc_id, "chunk_count": chunk_count},
            )
        except Exception as e:
            await task_service.update_task(
                db, task.id, user.id, status="failed", error=str(e)
            )
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

        # Choose chunking strategy
        total_text_len = sum(len(p.get("text", "")) for p in pages)
        rough_sentences = sum(
            len(re.split(r"(?<=[.!?。！？;；])\s+", p.get("text", ""))) for p in pages
        )
        method = _choose_chunker_method(total_text_len, rough_sentences)
        logger.debug(
            "Auto-selected chunking method: %s (len=%d, sentences=%d)",
            method,
            total_text_len,
            rough_sentences,
        )

        # Chunk
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

        # Build vector store
        logger.info("Building vector store...")
        store = DocumentVectorStore(doc_id, retrieval_type=DocumentVectorStore.RETRIEVAL_TYPE_HYBRID)
        await store.add_chunks(chunks)

        # Mark ready
        doc.status = "ready"
        doc.chunk_count = len(chunks)
        await db.commit()
        logger.info("Processing complete: %s (%d chunks)", doc_id, len(chunks))
        return len(chunks), method

    except Exception as e:
        # Mark the document as failed
        doc.status = "error"
        await db.commit()
        if isinstance(e, AppError):
            raise
        logger.error("document processing: %s", e, exc_info=True)
        raise ExternalServiceError(str(e))


async def list_documents(
    db: AsyncSession,
    user: User,
) -> list[Document]:
    """Return all documents owned by user, newest first."""
    result = await db.execute(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
) -> dict:
    """Get a single document with its chunks. Raises NotFoundError if missing."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    store = DocumentVectorStore(doc_id)
    await store.load()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "file_size": doc.file_size,
        "created_at": str(doc.created_at),
        "chunks": store._store.chunks if store._store.chunks else [],
    }


async def delete_document(
    db: AsyncSession,
    user: User,
    doc_id: str,
) -> None:
    """Delete a document, its file, and vector store. Throws NotFoundError if missing."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档不存在")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    store = DocumentVectorStore(doc_id)
    store.delete()

    await db.delete(doc)
    await db.commit()
