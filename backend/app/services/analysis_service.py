"""
Analysis service — weakness analysis, knowledge stats, progress tracking.
"""

from collections import defaultdict
from operator import itemgetter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Quiz, QuizResult, User


async def analyze_wrong_questions(
    db: AsyncSession,
    user: User,
) -> dict:
    """Analyze wrong answers and return weak areas with suggestions.

    薄弱点按题目所属文档聚合，topic 展示文档名（而非文档 UUID）。
    """
    result = await db.execute(
        select(QuizResult).where(QuizResult.user_id == user.id, QuizResult.is_correct == False)
    )
    wrong_results = list(result.scalars().all())

    if not wrong_results:
        return {"message": "暂无错题", "weak_areas": []}

    quiz_ids = [r.quiz_id for r in wrong_results]
    q_result = await db.execute(select(Quiz).where(Quiz.id.in_(quiz_ids)))
    quizzes = {q.id: q for q in q_result.scalars().all()}

    # 文档名映射：把 document_id 换成用户可读的文件名
    doc_ids = {q.document_id for q in quizzes.values() if q.document_id}
    doc_names: dict[str, str] = {}
    if doc_ids:
        d_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        doc_names = {d.id: d.filename for d in d_result.scalars().all()}

    topic_stats: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"wrong": 0, "total": 0}
    )

    for w in wrong_results:
        quiz = quizzes.get(w.quiz_id)
        if quiz:
            topic_stats[quiz.document_id]["wrong"] += 1

    all_r = await db.execute(select(QuizResult).where(QuizResult.user_id == user.id))
    all_results = all_r.scalars().all()

    for r in all_results:
        quiz = quizzes.get(r.quiz_id)
        if quiz:
            topic_stats[quiz.document_id]["total"] += 1

    weak_areas = []
    for doc_id, stats in topic_stats.items():
        if stats["total"] > 0:
            acc = (stats["total"] - stats["wrong"]) / stats["total"]
            suggestions = ["重新学习这部分内容", "多做相关练习"] if acc < 0.7 else ["保持练习"]
            weak_areas.append(
                {
                    "topic": doc_names.get(doc_id, "未知文档"),
                    "wrong_count": stats["wrong"],
                    "total_count": stats["total"],
                    "accuracy_rate": round(acc * 100, 1),
                    "suggestions": suggestions,
                }
            )

    weak_areas.sort(key=itemgetter("accuracy_rate"))
    return {"message": f"共{len(wrong_results)}道错题", "weak_areas": weak_areas[:5]}


async def get_knowledge_stats(
    db: AsyncSession,
    user: User,
) -> dict:
    """Return overall quiz accuracy stats."""
    result = await db.execute(select(QuizResult).where(QuizResult.user_id == user.id))
    all_results = list(result.scalars().all())

    total = len(all_results)
    correct = sum(1 for r in all_results if r.is_correct)
    acc = correct / total if total > 0 else 0

    return {
        "total_quizzes": total,
        "correct_count": correct,
        "accuracy_rate": round(acc * 100, 1),
    }


async def get_progress(
    db: AsyncSession,
    user: User,
) -> dict:
    """Return daily progress data (last 7 days) and total exercises."""
    result = await db.execute(select(QuizResult).where(QuizResult.user_id == user.id))
    all_results = list(result.scalars().all())

    total = len(all_results)
    daily: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "correct": 0}
    )
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
            "accuracy": round(s["correct"] / s["total"] * 100, 1) if s["total"] > 0 else 0,
        }
        for d, s in sorted(daily.items())
    ]

    return {"total_exercises": total, "progress_data": progress_data[-7:]}
