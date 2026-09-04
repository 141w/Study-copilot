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
    message_format: str = "openai"


class LLMConfigResp(BaseModel):
    id: str
    provider: str
    base_url: str | None = None
    model_name: str
    temperature: float
    max_tokens: int
    embedding_model: str
    embedding_dimension: int
    message_format: str = "openai"
    has_api_key: bool = False
    api_key_masked: str | None = None
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
        message_format=req.message_format,
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
        message_format=req.message_format,
    )
    return LLMConfigResp(**data)


# 安全修复（2026-08-19）：移除 GET /llm/with-secret 端点。
# 该端点会把解密后的 API Key 明文返回给前端（经浏览器/扩展/日志可截获）。
# 后端内部仍通过 config_service.get_llm_config_with_secret() 获取明文（chat/quiz/transform），
# 前端只需要 has_api_key / api_key_masked（见 GET /llm）。
