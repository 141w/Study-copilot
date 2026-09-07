from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.rate_limit import IPRateLimiter
from app.db import User, get_db
from app.exceptions import RateLimitError
from app.services import quiz_service

router = APIRouter(prefix="/quiz", tags=["做题"])

_quiz_limiter = IPRateLimiter(requests_per_minute=20)


# ── Schemas ────────────────────────────────────────────────────────────────


class QuizGenRequest(BaseModel):
    document_ids: list[str]
    choice_count: int | None = 3
    short_answer_count: int | None = 2
    config: dict | None = None

    @model_validator(mode="after")
    def _check_total_positive(self):
        cc = self.choice_count if self.choice_count is not None else 3
        sa = self.short_answer_count if self.short_answer_count is not None else 2
        if cc < 0 or sa < 0:
            raise ValueError("题目数量不能为负数")
        if cc + sa == 0:
            raise ValueError("选择题和简答题的数量不能同时为 0，请至少选择一种题型")
        return self


class QuizResp(BaseModel):
    id: str
    question_type: str
    question: str
    options: list[str] | None = None
    answer: str | None = None
    explanation: str | None = None


class QuizGenResp(BaseModel):
    quizzes: list[QuizResp]


class QuizSubmitReq(BaseModel):
    quiz_id: str
    user_answer: str


class QuizSubmitResp(BaseModel):
    quiz_id: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str | None = None


class QuizResultResp(BaseModel):
    quiz_id: str
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    submitted_at: str


class WrongQuizResp(BaseModel):
    quiz_id: str
    question: str
    question_type: str | None = "choice"
    options: list[str] | None = None
    user_answer: str
    correct_answer: str
    explanation: str | None = None
    submitted_at: str
    document_id: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/generate", response_model=QuizGenResp)
async def generate_quizzes(
    request: Request,
    req: QuizGenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _quiz_limiter.check(request):
        raise RateLimitError("请求过于频繁，请稍后再试")

    quizzes = await quiz_service.generate_quizzes(
        db,
        current_user,
        req.document_ids,
        req.choice_count if req.choice_count is not None else 3,
        req.short_answer_count if req.short_answer_count is not None else 2,
        req.config,
    )
    return QuizGenResp(quizzes=[QuizResp(**q) for q in quizzes])


@router.post("/submit", response_model=QuizSubmitResp)
async def submit(
    req: QuizSubmitReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await quiz_service.submit_answer(db, current_user, req.quiz_id, req.user_answer)
    return QuizSubmitResp(**result)


@router.get("/result-history", response_model=list[QuizResultResp])
async def get_hist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = await quiz_service.get_result_history(db, current_user)
    return [QuizResultResp(**r) for r in results]


@router.get("/wrong-questions", response_model=list[WrongQuizResp])
async def get_wrong_questions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = await quiz_service.get_wrong_questions(db, current_user)
    return [WrongQuizResp(**r) for r in results]
