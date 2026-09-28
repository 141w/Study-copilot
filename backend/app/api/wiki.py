"""阶段五 5.1：知识 Wiki API。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import wiki_service

router = APIRouter(prefix="/wiki", tags=["知识Wiki"])
logger = logging.getLogger(__name__)


class WikiCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    summary: str = ""
    page_type: str = "concept"
    status: str = "published"


class WikiUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    page_type: str | None = None
    status: str | None = None


class LinkResolveReq(BaseModel):
    slugs: list[str]


@router.get("")
async def list_wiki_pages(
    q: str | None = Query(default=None),
    page_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await wiki_service.list_pages(db, current_user, q=q, page_type=page_type)


@router.get("/resolve")
async def resolve_links(
    slugs: str = Query(..., description="逗号分隔的 slug 列表"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parts = [s.strip() for s in slugs.split(",") if s.strip()]
    return await wiki_service.resolve_links(db, current_user, parts)


@router.get("/by-slug/{slug}")
async def get_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await wiki_service.get_page_by_slug(db, current_user, slug)


@router.get("/{page_id}")
async def get_wiki_page(
    page_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await wiki_service.get_page(db, current_user, page_id)


@router.post("")
async def create_wiki_page(
    body: WikiCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await wiki_service.create_page(
        db,
        current_user,
        slug=body.slug,
        title=body.title,
        content=body.content,
        summary=body.summary,
        page_type=body.page_type,
        status=body.status,
    )


@router.put("/{page_id}")
async def update_wiki_page(
    page_id: str,
    body: WikiUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await wiki_service.update_page(
        db,
        current_user,
        page_id,
        title=body.title,
        content=body.content,
        summary=body.summary,
        page_type=body.page_type,
        status=body.status,
    )


@router.delete("/{page_id}")
async def delete_wiki_page(
    page_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await wiki_service.delete_page(db, current_user, page_id)
    return {"success": True}
