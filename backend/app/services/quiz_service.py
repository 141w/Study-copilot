"""
Quiz service — generate quizzes, submit answers, history, wrong questions.
"""

import json
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.config_service import get_llm_config_with_secret
from app.core.quiz_generator import QuizGenerator
from app.core.vector_store import DocumentVectorStore
from app.db import Document, Quiz, QuizResult, User
from app.exceptions import ExternalServiceError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


async def generate_quizzes(
    db: AsyncSession,
    user: User,
    document_ids: list[str],
    choice_count: int = 3,
    short_answer_count: int = 2,
    config: dict | None = None,
) -> list[dict]:
    """Generate quizzes from documents. Returns list of quiz dicts (without answers)."""
    if not document_ids:
        raise ValidationError("请选择文档")

    logger.debug(f"document_ids: {document_ids}")
    logger.debug(f"choice_count: {choice_count}, short_answer_count: {short_answer_count}")

    chunks_list = []
    for did in document_ids:
        result = await db.execute(
            select(Document).where(Document.id == did, Document.user_id == user.id)
        )
        doc = result.scalar_one_or_none()
        logger.debug(f"doc found: {doc}, status: {doc.status if doc else 'None'}")
        if doc and doc.status == "ready":
            store = DocumentVectorStore(did)
            await store.load()
            logger.debug(f"chunks count: {len(store._store.chunks)}")
            if store._store.chunks:
                chunks_list.extend([c["text"] for c in store._store.chunks[:10]])

    if not chunks_list:
        raise ValidationError("文档内容不足")

    ctx = "\n\n".join(chunks_list[:5])
    logger.debug(f"context length: {len(ctx)}")

    user_config = await get_llm_config_with_secret(db, user)
    llm_config = config if config else user_config

    try:
        qgen = QuizGenerator(llm_config) if llm_config else QuizGenerator()
        qdata = await qgen.generate_quizzes(ctx, choice_count, short_answer_count)
        logger.debug(f"generated quizzes: {len(qdata)}")
    except Exception as e:
        logger.error(f"generate_quizzes: {e}")
        import traceback

        traceback.print_exc()
        raise ExternalServiceError(f"生成题目失败: {str(e)}")

    saved = []
    for q in qdata:
        qid = str(uuid.uuid4())
        new_q = Quiz(
            id=qid,
            document_id=document_ids[0],
            question_type=q.get("question_type", "choice"),
            question=q.get("question", ""),
            options=json.dumps(q.get("options", [])) if q.get("options") else None,
            answer=q.get("answer", ""),
            explanation=q.get("explanation", ""),
        )
        db.add(new_q)
        saved.append(
            {
                "id": qid,
                "question_type": q.get("question_type", "choice"),
                "question": q.get("question", ""),
                "options": q.get("options"),
                "answer": None,
                "explanation": None,
            }
        )

    await db.commit()
    return saved


async def submit_answer(
    db: AsyncSession,
    user: User,
    quiz_id: str,
    user_answer: str,
) -> dict:
    """Submit an answer and evaluate correctness. Returns result dict."""
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("题目不存在")

    user_ans = user_answer.strip().lower()
    correct_ans = quiz.answer.strip().lower()

    user_letters = re.findall(r"[a-d]", user_ans)
    correct_letters = re.findall(r"[a-d]", correct_ans)

    user_ans_clean = user_ans.strip(".,!?，。、（）")
    correct_ans_clean = correct_ans.strip(".,!?，。、（）")

    is_correct = bool(
        user_ans_clean == correct_ans_clean
        or user_ans == correct_ans
        or (user_letters and set(user_letters) == set(correct_letters))
    )

    rec = QuizResult(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        user_id=user.id,
        user_answer=user_answer,
        is_correct=is_correct,
    )
    db.add(rec)
    await db.commit()

    return {
        "quiz_id": quiz_id,
        "user_answer": user_answer,
        "correct_answer": quiz.answer,
        "is_correct": is_correct,
        "explanation": quiz.explanation,
    }


async def get_result_history(
    db: AsyncSession,
    user: User,
) -> list[dict]:
    """Return the latest 100 quiz results with question text."""
    result = await db.execute(
        select(QuizResult)
        .where(QuizResult.user_id == user.id)
        .order_by(QuizResult.submitted_at.desc())
        .limit(100)
    )
    res = list(result.scalars().all())

    quiz_ids = [r.quiz_id for r in res]
    quiz_map = {}
    if quiz_ids:
        q_result = await db.execute(select(Quiz).where(Quiz.id.in_(quiz_ids)))
        for q in q_result.scalars().all():
            quiz_map[q.id] = q

    results = []
    for r in res:
        quiz = quiz_map.get(r.quiz_id)
        results.append(
            {
                "quiz_id": r.quiz_id,
                "question": quiz.question if quiz else "",
                "user_answer": r.user_answer,
                "correct_answer": quiz.answer if quiz else "",
                "is_correct": r.is_correct,
                "submitted_at": str(r.submitted_at),
            }
        )
    return results


async def get_wrong_questions(
    db: AsyncSession,
    user: User,
) -> list[dict]:
    """Return all incorrectly answered questions."""
    result = await db.execute(
        select(QuizResult)
        .where(QuizResult.user_id == user.id, QuizResult.is_correct == False)
        .order_by(QuizResult.submitted_at.desc())
    )
    res = list(result.scalars().all())

    quiz_ids = [r.quiz_id for r in res]
    quiz_map = {}
    if quiz_ids:
        q_result = await db.execute(select(Quiz).where(Quiz.id.in_(quiz_ids)))
        for q in q_result.scalars().all():
            quiz_map[q.id] = q

    results = []
    for r in res:
        quiz = quiz_map.get(r.quiz_id)
        if quiz:
            results.append(
                {
                    "quiz_id": r.quiz_id,
                    "question": quiz.question,
                    "question_type": quiz.question_type,
                    "options": json.loads(quiz.options) if quiz.options else None,
                    "user_answer": r.user_answer,
                    "correct_answer": quiz.answer,
                    "explanation": quiz.explanation,
                    "submitted_at": str(r.submitted_at),
                    "document_id": quiz.document_id,
                }
            )
    return results
