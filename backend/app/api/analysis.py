from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List
from collections import defaultdict

from app.db import get_db, QuizResult, Quiz
from app.api.auth import get_current_user, User

router = APIRouter(prefix="/analysis", tags=["分析"])


class Weakness(BaseModel):
    topic: str
    wrong_count: int
    total_count: int
    accuracy_rate: float
    suggestions: List[str]


class KnowledgeStats(BaseModel):
    total_quizzes: int
    correct_count: int
    accuracy_rate: float


@router.post("/wrong")
async def analyze_wrong(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(QuizResult).where(
            QuizResult.user_id == current_user.id, QuizResult.is_correct == False
        )
    )
    wrong_results = result.scalars().all()

    if not wrong_results:
        return {"message": "暂无错题", "weak_areas": []}

    quiz_ids = [r.quiz_id for r in wrong_results]
    q_result = await db.execute(select(Quiz).where(Quiz.id.in_(quiz_ids)))
    quizzes = {q.id: q for q in q_result.scalars().all()}

    topic_stats = defaultdict(lambda: {"wrong": 0, "total": 0})

    for w in wrong_results:
        quiz = quizzes.get(w.quiz_id)
        if quiz:
            topic_stats[quiz.document_id]["wrong"] += 1

    all_r = await db.execute(
        select(QuizResult).where(QuizResult.user_id == current_user.id)
    )
    all_results = all_r.scalars().all()

    for r in all_results:
        quiz = quizzes.get(r.quiz_id)
        if quiz:
            topic_stats[quiz.document_id]["total"] += 1

    weak_areas = []
    for topic, stats in topic_stats.items():
        if stats["total"] > 0:
            acc = (stats["total"] - stats["wrong"]) / stats["total"]
            suggestions = (
                ["重新学习这部分内容", "多做相关练习"] if acc < 0.7 else ["保持练习"]
            )
            weak_areas.append(
                Weakness(
                    topic=topic,
                    wrong_count=stats["wrong"],
                    total_count=stats["total"],
                    accuracy_rate=round(acc * 100, 1),
                    suggestions=suggestions,
                )
            )

    weak_areas.sort(key=lambda x: x.accuracy_rate)
    return {"message": f"共{len(wrong_results)}道错题", "weak_areas": weak_areas[:5]}


@router.get("/knowledge")
async def get_knowledge(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(QuizResult).where(QuizResult.user_id == current_user.id)
    )
    all_results = result.scalars().all()

    total = len(all_results)
    correct = sum(1 for r in all_results if r.is_correct)
    acc = correct / total if total > 0 else 0

    return KnowledgeStats(
        total_quizzes=total, correct_count=correct, accuracy_rate=round(acc * 100, 1)
    )


@router.get("/progress")
async def get_progress(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(QuizResult).where(QuizResult.user_id == current_user.id)
    )
    all_results = result.scalars().all()

    daily = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in all_results:
        date = str(r.submitted_at.date())
        daily[date]["total"] += 1
        if r.is_correct:
            daily[date]["correct"] += 1

    progress_data = [
        {
            "date": d,
            "total": s["total"],
            "correct": s["correct"],
            "accuracy": round(s["correct"] / s["total"] * 100, 1)
            if s["total"] > 0
            else 0,
        }
        for d, s in sorted(daily.items())
    ]

    return {"total_exercises": total, "progress_data": progress_data[-7:]}
