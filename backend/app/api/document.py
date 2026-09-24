from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.rate_limit import IPRateLimiter
from app.core.url_extractor import extract_from_url
from app.db import User, get_db
from app.exceptions import RateLimitError
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["文档"])

_upload_limiter = IPRateLimiter(requests_per_minute=10)


# ── Schemas ────────────────────────────────────────────────────────────────


class DocResponse(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    file_size: int
    created_at: str


class DocProcessResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str
    chunk_count: int


class UrlImportRequest(BaseModel):
    url: str


class ChunkPreviewRequest(BaseModel):
    text: str
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    strategy: str | None = "auto"


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/preview-chunking")
async def preview_chunking(
    data: ChunkPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """只读分块预览：不写库、不算向量。返回策略链、拒绝原因、画像与候选块。"""
    import asyncio

    from app.core.chunking_pipeline import (
        PREVIEW_MAX_CHARS,
        PREVIEW_MAX_CHUNKS,
        PREVIEW_TIMEOUT_S,
        chunk_stats,
        profile_to_dict,
        run_chunking_chain,
        serialize_chunks,
    )
    from app.exceptions import ValidationError

    text = data.text or ""
    if len(text) > PREVIEW_MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"文本超过预览上限 {PREVIEW_MAX_CHARS} 字符",
        )
    if not text.strip():
        raise ValidationError("文本不能为空")

    strategy = (data.strategy or "auto").lower()
    if strategy not in {"auto", "fixed", "semantic", "hierarchical"}:
        raise ValidationError("strategy 仅支持 auto|fixed|semantic|hierarchical")

    pages = [{"text": text, "page": 1}]
    try:
        run = await asyncio.wait_for(
            run_chunking_chain(
                pages,
                "preview",
                filename="",
                strategy=strategy,
                chunk_size=data.chunk_size,
                chunk_overlap=data.chunk_overlap,
                allow_embed=False,
            ),
            timeout=PREVIEW_TIMEOUT_S,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="分块预览超时（5s）")

    stats = chunk_stats(run.chunks, PREVIEW_MAX_CHUNKS)
    return {
        "selected_strategy": run.selected_strategy,
        "chain": run.chain,
        "rejected": run.rejected,
        "fallback_used": run.fallback_used,
        "profile": profile_to_dict(run.profile),
        "chunks": serialize_chunks(run.chunks, PREVIEW_MAX_CHUNKS),
        "stats": stats,
    }


@router.post("/upload", response_model=DocProcessResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _upload_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    content = await file.read()
    if not file.filename:
        raise HTTPException(status_code=422, detail="上传文件缺少文件名")
    result = await document_service.upload_document(db, current_user, file.filename, content)
    return DocProcessResponse(**result)


@router.get("", response_model=list[DocResponse])
async def list_docs(
    limit: int | None = Query(None, ge=1, le=200, description="分页大小；缺省返回全部"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = await document_service.list_documents(db, current_user, limit=limit, offset=offset)
    return [
        DocResponse(
            id=d.id,
            filename=d.filename,
            status=d.status,
            chunk_count=d.chunk_count,
            file_size=d.file_size,
            created_at=str(d.created_at),
        )
        for d in docs
    ]


@router.get("/{doc_id}")
async def get_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await document_service.get_document(db, current_user, doc_id)


@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await document_service.delete_document(db, current_user, doc_id)
    return {"message": "删除成功"}


@router.post("/{doc_id}/restore")
async def restore_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从回收站恢复软删除的文档。"""
    await document_service.restore_document(db, current_user, doc_id)
    return {"message": "恢复成功"}


@router.post("/{doc_id}/reprocess", response_model=DocProcessResponse)
async def reprocess_doc(
    request: Request,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新处理文档（清理旧切片并重新进入解析、切片与向量化流程）。"""
    if not _upload_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")
    result = await document_service.reprocess_document(db, current_user, doc_id)
    return DocProcessResponse(**result)


@router.post("/from-url", response_model=DocProcessResponse)
async def import_from_url(
    request: Request,
    data: UrlImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a document from a URL by extracting its content."""
    if not _upload_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    from app.exceptions import ValidationError

    if not data.url.strip():
        raise ValidationError("URL 不能为空")

    # Extract content from URL
    extracted = await extract_from_url(data.url)

    # Generate a filename from the title
    title = extracted.get("title", "webpage")
    # Sanitize filename
    import re

    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:100]
    filename = f"{safe_title}.txt"

    # Convert text to bytes for the existing upload pipeline
    content = extracted["text"].encode("utf-8")

    result = await document_service.upload_document(db, current_user, filename, content)
    return DocProcessResponse(**result)
