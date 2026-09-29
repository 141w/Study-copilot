"""阶段四：端到端评测台 API。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db

router = APIRouter(prefix="/evaluation", tags=["评测"])
logger = logging.getLogger(__name__)


class EvalRunRequest(BaseModel):
    document_ids: list[str] = Field(..., min_length=1)
    questions: list[str] = Field(..., min_length=1, max_length=200)
    # F3：必填期望答案（与 questions 等长），缺省拒绝出百分比
    expected: list[list[str]] | None = None
    top_k: int = Field(5, ge=1, le=20)


@router.post("/run")
async def run_eval(
    body: EvalRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检索评测：问题 × 期望文档 → hit@k / Recall@k / MRR（与 harness 同口径）。"""
    from app.services import eval_service

    # 透传用户检索参数（与生产问答路径一致）
    try:
        from app.services.config_service import get_retrieval_config

        retrieval_config = await get_retrieval_config(db, current_user)
    except Exception:  # noqa: BLE001
        retrieval_config = None

    return await eval_service.run_retrieval_eval(
        db,
        current_user,
        body.document_ids,
        body.questions,
        expected=body.expected,
        top_k=body.top_k,
        retrieval_config=retrieval_config,
    )
