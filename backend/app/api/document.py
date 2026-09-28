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
    tag_names: list[str] = []


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


class ChunkUpdateRequest(BaseModel):
    content: str
    expected_revision: int | None = None


class ChunkRevertRequest(BaseModel):
    revision: int
    expected_revision: int | None = None


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
    # 一次查出所有文档标签，避免 N+1
    from sqlalchemy import select as sa_select

    from app.db.database import Tag as TagModel
    from app.db.database import document_tags as dt

    tag_rows = (
        await db.execute(
            sa_select(dt.c.document_id, TagModel.name)
            .select_from(dt)
            .join(TagModel, dt.c.tag_id == TagModel.id)
            .where(dt.c.document_id.in_([d.id for d in docs] or [""]))
        )
    ).all()
    tags_by_doc: dict[str, list[str]] = {}
    for did, name in tag_rows:
        tags_by_doc.setdefault(did, []).append(name)
    return [
        DocResponse(
            id=d.id,
            filename=d.filename,
            status=d.status,
            chunk_count=d.chunk_count,
            file_size=d.file_size,
            created_at=str(d.created_at),
            tag_names=sorted(tags_by_doc.get(d.id, [])),
        )
        for d in docs
    ]


@router.get("/{doc_id}")
async def get_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await document_service.get_document(db, current_user, doc_id)
    # Enrich chunks with stable ids / edit state for the online editor.
    from app.services import chunk_service

    briefs = await chunk_service.list_chunk_briefs(db, current_user, doc_id)
    chunks = result.get("chunks") or []
    if len(chunks) == len(briefs):
        for c, b in zip(chunks, briefs):
            c["id"] = b["id"]
            c["content_revision"] = b["content_revision"]
            c["index_status"] = b["index_status"]
            c["char_start"] = b["char_start"]
            c["char_end"] = b["char_end"]
            c["is_parent"] = b["is_parent"]
    return result


@router.get("/{doc_id}/chunks/{chunk_id}")
async def get_chunk(
    doc_id: str,
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import chunk_service

    return await chunk_service.get_chunk(db, current_user, doc_id, chunk_id)


@router.put("/{doc_id}/chunks/{chunk_id}")
async def update_chunk(
    doc_id: str,
    chunk_id: str,
    data: ChunkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """乐观并发编辑：expected_revision 不匹配 → 409；响应含 index_status。"""
    from app.services import chunk_service

    return await chunk_service.update_chunk(
        db,
        current_user,
        doc_id,
        chunk_id,
        data.content,
        expected_revision=data.expected_revision,
    )


@router.post("/{doc_id}/chunks/{chunk_id}/revert")
async def revert_chunk(
    doc_id: str,
    chunk_id: str,
    data: ChunkRevertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """回滚到历史版本（实现为一次可再回滚的编辑）。"""
    from app.services import chunk_service

    return await chunk_service.revert_chunk(
        db,
        current_user,
        doc_id,
        chunk_id,
        data.revision,
        expected_revision=data.expected_revision,
    )


@router.get("/{doc_id}/chunks/{chunk_id}/revisions")
async def list_chunk_revisions(
    doc_id: str,
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import chunk_service

    return await chunk_service.list_revisions(db, current_user, doc_id, chunk_id)


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


# ── 5.6 聊天会话临时附件（仅追加；勿与 /{doc_id} 单段路由冲突） ─────────────


class ChatAttachmentResp(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    size: int | None = None
    session_id: str | None = None
    created_at: str | None = None
    has_text: bool = False


@router.post("/chat-attachments/upload", response_model=ChatAttachmentResp)
async def upload_chat_attachment(
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """5.6：会话级临时附件上传。两阶段状态：uploaded/parsing → ready。"""
    if not _upload_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")
    from app.services import chat_service

    content = await file.read()
    if not file.filename:
        raise HTTPException(status_code=422, detail="上传文件缺少文件名")
    meta = await chat_service.save_chat_attachment(
        current_user, file.filename, content, session_id=session_id
    )
    return ChatAttachmentResp(**meta)


@router.get("/chat-attachments/list", response_model=list[ChatAttachmentResp])
async def list_chat_attachments(
    session_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """5.6：列出当前用户的会话临时附件。"""
    from app.services import chat_service

    items = await chat_service.list_chat_attachments(current_user, session_id=session_id)
    return [ChatAttachmentResp(**m) for m in items]


@router.get("/chat-attachments/{attachment_id}", response_model=ChatAttachmentResp)
async def get_chat_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """5.6：查询附件状态（解析可稍后完成，不阻塞发送）。"""
    from app.services import chat_service

    meta = await chat_service.get_chat_attachment(current_user, attachment_id)
    return ChatAttachmentResp(**meta)


@router.delete("/chat-attachments/{attachment_id}")
async def delete_chat_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """5.6：删除会话临时附件。"""
    from app.services import chat_service

    await chat_service.delete_chat_attachment(current_user, attachment_id)
    return {"message": "附件已删除"}


# ── 阶段二：文档标签 ──────────────────────────────────────────────────────


class DocTagsUpdate(BaseModel):
    tag_names: list[str]


class BatchTagRequest(BaseModel):
    document_ids: list[str]
    tag_names: list[str]


class DocTagsResp(BaseModel):
    document_id: str
    tag_names: list[str]


@router.get("/{doc_id}/tags", response_model=DocTagsResp)
async def get_doc_tags(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import document_tag_service

    names = await document_tag_service.list_document_tag_names(db, current_user, doc_id)
    return DocTagsResp(document_id=doc_id, tag_names=names)


@router.put("/{doc_id}/tags", response_model=DocTagsResp)
async def put_doc_tags(
    doc_id: str,
    body: DocTagsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import document_tag_service

    names = await document_tag_service.set_document_tags(db, current_user, doc_id, body.tag_names)
    return DocTagsResp(document_id=doc_id, tag_names=names)


@router.post("/{doc_id}/auto-tag", response_model=DocTagsResp)
async def auto_tag_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从已有标签池自动匹配（只增不覆盖人工标签）。"""
    from app.services import document_tag_service

    added = await document_tag_service.auto_tag_document(db, current_user, doc_id)
    all_names = await document_tag_service.list_document_tag_names(db, current_user, doc_id)
    return DocTagsResp(document_id=doc_id, tag_names=all_names or added)


@router.post("/batch-tag")
async def batch_tag_docs(
    body: BatchTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import document_tag_service

    if len(body.document_ids) > 100:
        raise RateLimitError("单次最多 100 篇")
    result = await document_tag_service.batch_add_tags(
        db, current_user, body.document_ids, body.tag_names
    )
    return {"results": result}


@router.post("/batch-auto-tag")
async def batch_auto_tag_docs(
    body: BatchTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量自动打标。tag_names 忽略；document_ids 为目标题。"""
    from app.services import document_tag_service

    if len(body.document_ids) > 50:
        raise RateLimitError("单次最多 50 篇")
    result = await document_tag_service.batch_auto_tag(db, current_user, body.document_ids)
    return {"results": result}


@router.get("/{doc_id}/parse-spans")
async def get_parse_spans(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """阶段三：解析进度时间线（最近若干次 attempt）。"""
    from app.services import document_tag_service, parse_span_service

    await document_tag_service._owned_document(db, current_user, doc_id)
    spans = await parse_span_service.list_parse_spans(db, doc_id)
    return {"document_id": doc_id, "spans": spans}
