"""
Analysis service — weakness analysis, knowledge stats, progress tracking.
"""

from collections import defaultdict
from operator import itemgetter

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, Quiz, QuizResult, User


async def analyze_wrong_questions(
    db: AsyncSession,
    user: User,
) -> dict:
    """Analyze wrong answers and return weak areas with suggestions.

    薄弱点按题目所属文档聚合，topic 展示文档名（而非文档 UUID）。

    优化：用两条 SQL 聚合替代 4 次全表扫描（H-1）。
    """
    # ── 聚合 1：各文档错题数 ──
    wrong_stmt = (
        select(
            Quiz.document_id,
            func.count(QuizResult.id).label("wrong"),
        )
        .join(Quiz, QuizResult.quiz_id == Quiz.id)
        .where(
            QuizResult.user_id == user.id,
            QuizResult.is_correct == False,
        )
        .group_by(Quiz.document_id)
    )
    wrong_rows = (await db.execute(wrong_stmt)).all()

    # ── 聚合 2：各文档总题数 ──
    total_stmt = (
        select(
            Quiz.document_id,
            func.count(QuizResult.id).label("total"),
        )
        .join(Quiz, QuizResult.quiz_id == Quiz.id)
        .where(QuizResult.user_id == user.id)
        .group_by(Quiz.document_id)
    )
    total_rows = (await db.execute(total_stmt)).all()

    if not total_rows:
        return {"message": "暂无答题记录", "weak_areas": []}

    # 查文档名（只查有答题的文档）
    doc_ids = {r.document_id for r in total_rows if r.document_id}
    doc_names: dict[str, str] = {}
    if doc_ids:
        d_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        doc_names = {d.id: d.filename for d in d_result.scalars().all()}

    # 合并
    wrong_map = {r.document_id: r.wrong for r in wrong_rows}
    topic_stats: dict[str, dict[str, int]] = {}
    for r in total_rows:
        did = r.document_id or ""
        topic_stats[did] = {
            "wrong": wrong_map.get(did, 0),
            "total": r.total,
        }

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
    total_wrong = sum(r.wrong for r in wrong_rows)
    return {"message": f"共{total_wrong}道错题", "weak_areas": weak_areas[:5]}


async def get_knowledge_stats(
    db: AsyncSession,
    user: User,
) -> dict:
    """Return overall quiz accuracy stats. 优化：单条 SQL 聚合（H-1）。"""
    stmt = select(
        func.count(QuizResult.id).label("total"),
        func.sum(case((QuizResult.is_correct == True, 1), else_=0)).label("correct"),
    ).where(QuizResult.user_id == user.id)
    result = await db.execute(stmt)
    row = result.one()
    total = int(row.total or 0)
    correct = int(row.correct or 0)
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
    """Return daily progress data (last 7 days) and total exercises.

    优化：SQL 层按日期聚合，不拉全表（H-1）。
    """
    stmt = (
        select(
            func.date(QuizResult.submitted_at).label("date"),
            func.count(QuizResult.id).label("total"),
            func.sum(case((QuizResult.is_correct == True, 1), else_=0)).label("correct"),
        )
        .where(QuizResult.user_id == user.id)
        .group_by(func.date(QuizResult.submitted_at))
        .order_by(func.date(QuizResult.submitted_at))
    )
    rows = (await db.execute(stmt)).all()

    progress_data = [
        {
            "date": str(r.date),
            "total": r.total,
            "correct": int(r.correct or 0),
            "accuracy": round(int(r.correct or 0) / r.total * 100, 1) if r.total > 0 else 0,
        }
        for r in rows
    ]

    total_exercises = sum(r.total for r in rows)
    return {"total_exercises": total_exercises, "progress_data": progress_data[-7:]}
