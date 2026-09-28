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
    questions: list[str] = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


@router.post("/run")
async def run_eval(
    body: EvalRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检索评测：问题 × 文档 → hit@k / top 结果（与 retrieval_probe 同口径）。"""
    from app.services import eval_service

    return await eval_service.run_retrieval_eval(
        db, current_user, body.document_ids, body.questions, top_k=body.top_k
    )
