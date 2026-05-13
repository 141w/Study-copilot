from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List
import uuid
import os
import aiofiles

from app.db import get_db, User, Document
from app.api.auth import get_current_user
from app.core.document_parser import document_parser
from app.core.chunker import text_chunker
from app.core.vector_store import DocumentVectorStore
from app.core.rate_limit import IPRateLimiter
from app.config import settings

router = APIRouter(prefix="/documents", tags=["文档"])

# 创建限流器
_upload_limiter = IPRateLimiter(requests_per_minute=10)


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


@router.post("/upload", response_model=DocProcessResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 手动限流检查
    if not _upload_limiter.check(request):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    # 检查文件格式支持
    if not document_parser.is_supported(file.filename):
        supported = ", ".join(document_parser.supported_extensions)
        raise HTTPException(
            status_code=400, detail=f"不支持的文件格式，仅支持: {supported}"
        )

    doc_id = str(uuid.uuid4())
    uploads_dir = "./uploads"
    user_dir = os.path.join(uploads_dir, current_user.id)
    os.makedirs(user_dir, exist_ok=True)

    # 根据文件类型确定扩展名
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else ""
    fp = os.path.join(user_dir, f"{doc_id}.{ext}")

    content = await file.read()
    file_size = len(content)

    # 检查文件大小
    if file_size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 {settings.max_file_size // 1024 // 1024}MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    async with aiofiles.open(fp, "wb") as f:
        await f.write(content)

    print(f"[DEBUG] File saved to: {fp}, exists: {os.path.exists(fp)}")

    try:
        # 使用统一解析器
        try:
            pages = await document_parser.extract_pages(fp)
            print(f"[DEBUG] Extracted {len(pages)} pages")
            if pages:
                print(
                    f"[DEBUG] First page text preview: {pages[0].get('text', '')[:200]}"
                )
            else:
                print(f"[ERROR] No pages extracted from {fp}")
                raise HTTPException(status_code=400, detail="无法从文档中提取文本内容")
        except Exception as e:
            print(f"[ERROR] Failed to extract pages: {e}")
            raise HTTPException(status_code=500, detail=f"文档解析失败: {str(e)}")

        # 使用语义分块（可选，默认使用固定分块）
        # chunks = await SemanticChunker().chunk_document(pages, doc_id)
        try:
            chunks = text_chunker.chunk_document(pages, doc_id)
            print(f"[DEBUG] Created {len(chunks)} chunks")
            if chunks:
                print(
                    f"[DEBUG] First chunk text preview: {chunks[0].get('text', '')[:200]}"
                )
            else:
                print(f"[ERROR] No chunks created from pages")
                raise HTTPException(
                    status_code=400, detail="文档内容不足，无法生成知识块"
                )
        except Exception as e:
            print(f"[ERROR] Failed to chunk document: {e}")
            raise HTTPException(status_code=500, detail=f"文档分块失败: {str(e)}")

        # 创建FAISS向量库
        store = DocumentVectorStore(
            doc_id, retrieval_type=DocumentVectorStore.RETRIEVAL_TYPE_FAISS
        )
        await store.add_chunks(chunks)

        from app.db import Document

        new_doc = Document(
            id=doc_id,
            user_id=current_user.id,
            filename=file.filename,
            file_path=fp,
            status="ready",
            chunk_count=len(chunks),
            file_size=file_size,
        )
        db.add(new_doc)
        await db.commit()
        print(
            f"[DEBUG] Document saved to DB: id={doc_id}, chunks={len(chunks)}, file_size={file_size}"
        )

        return DocProcessResponse(
            id=doc_id,
            filename=file.filename,
            status="ready",
            message="上传成功",
            chunk_count=len(chunks),
        )
    except Exception as e:
        import traceback

        print(f"[ERROR] upload: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[DocResponse])
async def list_docs(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

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
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

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


@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    store = DocumentVectorStore(doc_id)
    store.delete()

    await db.delete(doc)
    await db.commit()

    return {"message": "删除成功"}
