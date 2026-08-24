from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import analysis_service

router = APIRouter(prefix="/analysis", tags=["分析"])


# ── Schemas ────────────────────────────────────────────────────────────────


class Weakness(BaseModel):
    topic: str
    wrong_count: int
    total_count: int
    accuracy_rate: float
    suggestions: list[str]


class KnowledgeStats(BaseModel):
    total_quizzes: int
    correct_count: int
    accuracy_rate: float


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/wrong")
async def analyze_wrong(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await analysis_service.analyze_wrong_questions(db, current_user)


@router.get("/knowledge")
async def get_knowledge(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await analysis_service.get_knowledge_stats(db, current_user)
    return KnowledgeStats(**data)


@router.get("/progress")
async def get_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await analysis_service.get_progress(db, current_user)
