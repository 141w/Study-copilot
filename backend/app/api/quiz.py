from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json

from app.db import get_db, Document, Quiz, QuizResult
from app.api.auth import get_current_user, User
from app.core.quiz_generator import QuizGenerator
from app.core.vector_store import DocumentVectorStore
from app.core.config import get_user_llm_config
from app.core.rate_limit import IPRateLimiter

router = APIRouter(prefix="/quiz", tags=["做题"])

# 创建限流器
_quiz_limiter = IPRateLimiter(requests_per_minute=20)


class QuizGenRequest(BaseModel):
    document_ids: List[str]
    choice_count: Optional[int] = 3
    short_answer_count: Optional[int] = 2
    config: Optional[dict] = None


class QuizResp(BaseModel):
    id: str
    question_type: str
    question: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None


class QuizGenResp(BaseModel):
    quizzes: List[QuizResp]


class QuizSubmitReq(BaseModel):
    quiz_id: str
    user_answer: str


class QuizSubmitResp(BaseModel):
    quiz_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None


class QuizResultResp(BaseModel):
    quiz_id: str
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    submitted_at: str


@router.post("/generate", response_model=QuizGenResp)
async def generate_quizzes(
    request: Request,
    req: QuizGenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 手动限流检查
    if not _quiz_limiter.check(request):
        raise HTTPException(
            status_code=429, 
            detail="请求过于频繁，请稍后再试"
        )
    if not req.document_ids:
        raise HTTPException(status_code=400, detail="请选择文档")

    print(f"[DEBUG] document_ids: {req.document_ids}")
    print(f"[DEBUG] choice_count: {req.choice_count}, short_answer_count: {req.short_answer_count}")

    chunks_list = []
    for did in req.document_ids:
        result = await db.execute(
            select(Document).where(
                Document.id == did, Document.user_id == current_user.id
            )
        )
        doc = result.scalar_one_or_none()
        print(f"[DEBUG] doc found: {doc}, status: {doc.status if doc else 'None'}")
        if doc and doc.status == "ready":
            store = DocumentVectorStore(did)
            await store.load()
            print(f"[DEBUG] chunks count: {len(store._store.chunks)}")
            if store._store.chunks:
                chunks_list.extend([c["text"] for c in store._store.chunks[:10]])

    if not chunks_list:
        raise HTTPException(status_code=400, detail="文档内容不足")

    ctx = "\n\n".join(chunks_list[:5])
    print(f"[DEBUG] context length: {len(ctx)}")

    # 获取用户配置
    user_config = await get_user_llm_config(db, current_user.id)
    llm_config = req.config if req.config else user_config

    try:
        qgen = QuizGenerator(llm_config) if llm_config else QuizGenerator()
        qdata = await qgen.generate_quizzes(
            ctx, req.choice_count, req.short_answer_count
        )
        print(f"[DEBUG] generated quizzes: {len(qdata)}")
    except Exception as e:
        print(f"[ERROR] generate_quizzes: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成题目失败: {str(e)}")

    saved = []
    for q in qdata:
        qid = str(uuid.uuid4())
        new_q = Quiz(
            id=qid,
            document_id=req.document_ids[0],
            question_type=q.get("question_type", "choice"),
            question=q.get("question", ""),
            options=json.dumps(q.get("options", [])) if q.get("options") else None,
            answer=q.get("answer", ""),
            explanation=q.get("explanation", ""),
        )
        db.add(new_q)
        saved.append(
            QuizResp(
                id=qid,
                question_type=q.get("question_type", "choice"),
                question=q.get("question", ""),
                options=q.get("options"),
                answer=None,
                explanation=None,
            )
        )

    await db.commit()
    return QuizGenResp(quizzes=saved)


@router.post("/submit", response_model=QuizSubmitResp)
async def submit(
    req: QuizSubmitReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Quiz).where(Quiz.id == req.quiz_id))
    quiz = result.scalar_one_or_none()

    if not quiz:
        raise HTTPException(status_code=404, detail="题目不存在")

    user_ans = req.user_answer.strip().lower()
    correct_ans = quiz.answer.strip().lower()

    # 提取字母 (A/B/C/D)
    import re
    user_letters = re.findall(r'[a-d]', user_ans)
    correct_letters = re.findall(r'[a-d]', correct_ans)

    # 完全匹配 或 字母匹配
    user_ans_clean = user_ans.strip('.,!?，。、（）')
    correct_ans_clean = correct_ans.strip('.,!?，。、（）')

    is_correct = (
        user_ans_clean == correct_ans_clean or
        user_ans == correct_ans or
        (user_letters and set(user_letters) == set(correct_letters))
    )

    rec = QuizResult(
        id=str(uuid.uuid4()),
        quiz_id=req.quiz_id,
        user_id=current_user.id,
        user_answer=req.user_answer,
        is_correct=is_correct,
    )
    db.add(rec)
    await db.commit()

    return QuizSubmitResp(
        quiz_id=req.quiz_id,
        user_answer=req.user_answer,
        correct_answer=quiz.answer,
        is_correct=is_correct,
        explanation=quiz.explanation,
    )


@router.get("/history")
async def get_quiz_history(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取做题历史记录"""
    result = await db.execute(
        select(QuizResult)
        .where(QuizResult.user_id == current_user.id)
        .order_by(QuizResult.submitted_at.desc())
    )
    res = result.scalars().all()

    results = []
    for r in res:
        q_result = await db.execute(select(Quiz).where(Quiz.id == r.quiz_id))
        quiz = q_result.scalar_one_or_none()
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


@router.get("/result-history", response_model=List[QuizResultResp])
async def get_hist(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(QuizResult)
        .where(QuizResult.user_id == current_user.id)
        .order_by(QuizResult.submitted_at.desc())
        .limit(100)
    )
    res = result.scalars().all()

    results = []
    for r in res:
        q_result = await db.execute(select(Quiz).where(Quiz.id == r.quiz_id))
        quiz = q_result.scalar_one_or_none()
        results.append(
            QuizResultResp(
                quiz_id=r.quiz_id,
                question=quiz.question if quiz else "",
                user_answer=r.user_answer,
                correct_answer=quiz.answer if quiz else "",
                is_correct=r.is_correct,
                submitted_at=str(r.submitted_at),
            )
        )

    return results


class WrongQuizResp(BaseModel):
    quiz_id: str
    question: str
    user_answer: str
    correct_answer: str
    explanation: Optional[str] = None
    submitted_at: str
    document_id: Optional[str] = None


@router.get("/wrong-questions", response_model=List[WrongQuizResp])
async def get_wrong_questions(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取错题列表"""
    result = await db.execute(
        select(QuizResult)
        .where(QuizResult.user_id == current_user.id, QuizResult.is_correct == False)
        .order_by(QuizResult.submitted_at.desc())
    )
    res = result.scalars().all()

    results = []
    for r in res:
        q_result = await db.execute(select(Quiz).where(Quiz.id == r.quiz_id))
        quiz = q_result.scalar_one_or_none()
        if quiz:
            results.append(
                WrongQuizResp(
                    quiz_id=r.quiz_id,
                    question=quiz.question,
                    user_answer=r.user_answer,
                    correct_answer=quiz.answer,
                    explanation=quiz.explanation,
                    submitted_at=str(r.submitted_at),
                    document_id=quiz.document_id,
                )
            )

    return results
