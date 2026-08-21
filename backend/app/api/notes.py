from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import note_service

router = APIRouter(prefix="/notes", tags=["笔记"])


# ── Schemas ─────────────────────────────────────────────────────────────


class NoteCreate(BaseModel):
    title: str
    content: str = ""
    course_space_id: str | None = None
    course_id: str | None = None  # frontend sends this; maps to course_space_id in view
    note_type: str = "markdown"
    tag_names: list[str] | None = None
    tags: list[str] | None = None  # frontend sends this; maps to tag_names in view


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    course_space_id: str | None = None
    course_id: str | None = None  # frontend alias
    note_type: str | None = None
    is_pinned: bool | None = None
    tag_names: list[str] | None = None
    tags: list[str] | None = None  # frontend alias


class TagResponse(BaseModel):
    id: str
    name: str
    created_at: str


class NoteSearchRequest(BaseModel):
    """Request for semantic note search."""
    query: str
    top_k: int = 5


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    course_space_id: str | None
    note_type: str
    is_pinned: bool
    tags: list[TagResponse]
    created_at: str
    updated_at: str


class NoteBrief(BaseModel):
    id: str
    title: str
    course_space_id: str | None
    note_type: str
    is_pinned: bool
    tags: list[str]  # string names for frontend compatibility
    created_at: str
    updated_at: str


def _tag_to_response(tag) -> TagResponse:
    return TagResponse(id=tag.id, name=tag.name, created_at=str(tag.created_at))


def _note_to_response(note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        course_space_id=note.course_space_id,
        note_type=note.note_type,
        is_pinned=note.is_pinned,
        tags=[_tag_to_response(t) for t in note.tags],
        created_at=str(note.created_at),
        updated_at=str(note.updated_at),
    )


def _note_to_brief(note) -> NoteBrief:
    return NoteBrief(
        id=note.id,
        title=note.title,
        course_space_id=note.course_space_id,
        note_type=note.note_type,
        is_pinned=note.is_pinned,
        tags=[t.name for t in (note.tags or [])],
        created_at=str(note.created_at),
        updated_at=str(note.updated_at),
    )


# ── Note Endpoints ──────────────────────────────────────────────────────


@router.post("", response_model=NoteResponse)
async def create_note(
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Normalize frontend field aliases
    csid = data.course_space_id or data.course_id
    tn = data.tag_names or data.tags
    note = await note_service.create_note(
        db,
        current_user,
        title=data.title,
        content=data.content,
        course_space_id=csid,
        note_type=data.note_type,
        tag_names=tn,
    )
    # Re-fetch with tags loaded
    note = await note_service.get_note(db, current_user, note.id)
    return _note_to_response(note)


@router.get("", response_model=list[NoteBrief])
async def list_notes(
    course_space_id: str | None = Query(None),
    tag: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notes = await note_service.list_notes(db, current_user, course_space_id, tag)
    return [_note_to_brief(n) for n in notes]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = await note_service.get_note(db, current_user, note_id)
    return _note_to_response(note)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Normalize frontend field aliases
    csid = data.course_space_id or data.course_id
    tn = data.tag_names or data.tags
    note = await note_service.update_note(
        db,
        current_user,
        note_id,
        title=data.title,
        content=data.content,
        course_space_id=csid,
        note_type=data.note_type,
        is_pinned=data.is_pinned,
        tag_names=tn,
    )
    return _note_to_response(note)


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await note_service.delete_note(db, current_user, note_id)
    return {"message": "删除成功"}




@router.post("/search", response_model=list[dict])
async def search_notes(
    req: NoteSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Semantic search across user notes."""
    results = await note_service.search_notes(db, current_user, req.query, req.top_k)
    return results


# ── Tag Endpoints ───────────────────────────────────────────────────────


@router.get("/tags/all", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tags = await note_service.list_tags(db, current_user)
    return [_tag_to_response(t) for t in tags]


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await note_service.delete_tag(db, current_user, tag_id)
    return {"message": "标签删除成功"}