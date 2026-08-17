from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import User, get_db
from app.services import config_service

router = APIRouter(prefix="/config", tags=["配置"])


# ── Schemas ────────────────────────────────────────────────────────────────


class LLMConfigReq(BaseModel):
    provider: str = "openrouter"
    api_key: str | None = None
    base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2048
    embedding_model: str = "shibing624/text2vec-base-chinese"
    embedding_dimension: int = 768


class LLMConfigResp(BaseModel):
    id: str
    provider: str
    model_name: str
    temperature: float
    max_tokens: int
    embedding_model: str
    embedding_dimension: int
    created_at: str
    updated_at: str


class LLMConfigWithSecret(BaseModel):
    id: str
    provider: str
    api_key: str | None
    base_url: str | None
    model_name: str
    temperature: float
    max_tokens: int
    embedding_model: str
    embedding_dimension: int
    created_at: str
    updated_at: str


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/llm", response_model=LLMConfigResp)
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await config_service.get_llm_config(db, current_user)
    return LLMConfigResp(**data)


@router.post("/llm", response_model=LLMConfigResp)
async def create_llm_config(
    req: LLMConfigReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await config_service.create_or_update_llm_config(
        db,
        current_user,
        req.provider,
        req.api_key,
        req.base_url,
        req.model_name,
        req.temperature,
        req.max_tokens,
        req.embedding_model,
        req.embedding_dimension,
    )
    return LLMConfigResp(**data)


@router.put("/llm", response_model=LLMConfigResp)
async def update_llm_config(
    req: LLMConfigReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await config_service.update_llm_config(
        db,
        current_user,
        req.provider,
        req.api_key,
        req.base_url,
        req.model_name,
        req.temperature,
        req.max_tokens,
        req.embedding_model,
        req.embedding_dimension,
    )
    return LLMConfigResp(**data)


@router.get("/llm/with-secret", response_model=LLMConfigWithSecret)
async def get_llm_config_with_secret(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await config_service.get_llm_config_with_secret(db, current_user)
    return LLMConfigWithSecret(**data)
