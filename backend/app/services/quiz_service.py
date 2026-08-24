"""
Quiz service — generate quizzes, submit answers, history, wrong questions.
"""

import json
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quiz_generator import QuizGenerator
from app.core.vector_store import DocumentVectorStore
from app.db import Document, Quiz, QuizResult, User
from app.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.services.config_service import get_llm_config_with_secret

logger = logging.getLogger(__name__)


async def generate_quizzes(
    db: AsyncSession,
    user: User,
    document_ids: list[str],
    choice_count: int = 3,
    short_answer_count: int = 2,
    config: dict | None = None,
) -> list[dict]:
    """Generate quizzes from documents. Returns list of quiz dicts (without answers).

    A task record is created to track the generation so it shows up in the
    task board. Generation itself runs inline because the frontend expects
    the quizzes in the response.
    """
    if not document_ids:
        raise ValidationError("请选择文档")

    from app.services import task_service

    task = await task_service.create_task(
        db,
        user.id,
        "quiz_generate",
        {"document_ids": document_ids, "choice_count": choice_count,
         "short_answer_count": short_answer_count},
    )
    await task_service.update_task(db, task.id, user.id, status="running")

    try:
        saved = await _do_generate_quiz(
            db, user, document_ids, choice_count, short_answer_count, config
        )
        await task_service.update_task(
            db, task.id, user.id, status="completed",
            result={"quiz_count": len(saved)},
        )
        return saved
    except Exception as e:
        await task_service.update_task(
            db, task.id, user.id, status="failed", error=str(e)
        )
        raise


async def _do_generate_quiz(
    db: AsyncSession,
    user: User,
    document_ids: list[str],
    choice_count: int = 3,
    short_answer_count: int = 2,
    config: dict | None = None,
) -> list[dict]:
    """Core quiz generation logic: gather context, call LLM, persist quizzes."""
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


def _judge_choice(user_answer: str, correct_answer: str) -> bool:
    """选择题判分：选项字母匹配（容忍大小写与标点）。"""
    user_ans = user_answer.strip().lower()
    correct_ans = correct_answer.strip().lower()

    user_letters = re.findall(r"[a-d]", user_ans)
    correct_letters = re.findall(r"[a-d]", correct_ans)

    user_ans_clean = user_ans.strip(".,!?，。、（）")
    correct_ans_clean = correct_ans.strip(".,!?，。、（）")

    return bool(
        user_ans_clean == correct_ans_clean
        or user_ans == correct_ans
        or (user_letters and set(user_letters) == set(correct_letters))
    )


async def _judge_short_answer(
    db: AsyncSession,
    user: User,
    quiz: Quiz,
    user_answer: str,
) -> tuple[bool, str | None]:
    """简答题判分：先做快速规则匹配，再用 LLM 语义判定。

    Returns (is_correct, judge_reason)。LLM 不可用时回退到规则匹配。
    """
    user_ans = user_answer.strip()
    correct_ans = (quiz.answer or "").strip()

    if not user_ans:
        return False, None

    # 规则 1：完全一致
    if user_ans.lower() == correct_ans.lower():
        return True, None

    # 规则 2：一方完整包含另一方（被包含方需有实质内容）
    shorter, longer = sorted([user_ans, correct_ans], key=len)
    if len(shorter) >= 2 and shorter.lower() in longer.lower():
        return True, None

    # 规则 3：LLM 语义判分（仅当用户真实配置了 LLM 时才调用）
    try:
        from app.core.llm import LLM
        from app.core.template_manager import render_template
        from app.db import UserLLMConfig

        # 修复（2026-08-19 E2E 发现）：get_llm_config_with_secret 在无配置时返回默认 dict，
        # 旧代码据此构造 LLM 会 fallback 到 settings 的 dummy key 发起真实 HTTP 调用，
        # 导致无 LLM 配置的用户提交简答题时请求挂起超时。
        # 先查用户是否真实保存了配置（含 api_key），没有则直接走规则回退。
        cfg_result = await db.execute(
            select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
        )
        cfg_row = cfg_result.scalar_one_or_none()
        if not cfg_row or not cfg_row.api_key:
            logger.info("judge_short_answer: user has no LLM config, skip LLM judge")
            return False, None

        user_config = await get_llm_config_with_secret(db, user) or {}
        llm = LLM(
            api_key=user_config.get("api_key"),
            base_url=user_config.get("base_url"),
            model=user_config.get("model_name"),
        )

        prompt = render_template(
            "quiz/judge_short_answer.jinja2",
            question=quiz.question,
            correct_answer=correct_ans,
            user_answer=user_ans,
        )
        resp = await llm.generate(prompt, temperature=0.0, max_tokens=200)

        match = re.search(r"\{[\s\S]*\}", resp)
        if match:
            data = json.loads(match.group())
            return bool(data.get("is_correct", False)), data.get("reason")
        logger.warning("judge_short_answer: no JSON in LLM response: %s", resp[:200])
    except Exception as e:
        logger.error("judge_short_answer LLM failed, fallback to exact match: %s", e)

    # 回退：LLM 不可用时保持严格匹配（已在规则 1/2 中覆盖），判为错误
    return False, None


async def submit_answer(
    db: AsyncSession,
    user: User,
    quiz_id: str,
    user_answer: str,
) -> dict:
    """Submit an answer and evaluate correctness. Returns result dict.

    选择题用选项字母匹配；简答题先规则匹配、再 LLM 语义判分。
    """
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise NotFoundError("题目不存在")

    judge_reason: str | None = None
    if quiz.question_type == "short_answer":
        is_correct, judge_reason = await _judge_short_answer(db, user, quiz, user_answer)
    else:
        is_correct = _judge_choice(user_answer, quiz.answer)

    rec = QuizResult(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        user_id=user.id,
        user_answer=user_answer,
        is_correct=is_correct,
    )
    db.add(rec)
    await db.commit()

    # 简答题通常没有预置解析，用 LLM 判定理由补充
    explanation = quiz.explanation
    if judge_reason and not explanation:
        explanation = f"判定理由：{judge_reason}"

    return {
        "quiz_id": quiz_id,
        "user_answer": user_answer,
        "correct_answer": quiz.answer,
        "is_correct": is_correct,
        "explanation": explanation,
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
