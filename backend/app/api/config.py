from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from app.db import get_db, UserLLMConfig
from app.api.auth import get_current_user, User

router = APIRouter(prefix="/config", tags=["配置"])


class LLMConfigReq(BaseModel):
    provider: str = "openrouter"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "gpt-4o-mini"
    temperature: int = 7
    max_tokens: int = 2048


class LLMConfigResp(BaseModel):
    id: str
    provider: str
    model_name: str
    temperature: int
    max_tokens: int
    created_at: str
    updated_at: str


class LLMConfigWithSecret(BaseModel):
    id: str
    provider: str
    api_key: Optional[str]
    base_url: Optional[str]
    model_name: str
    temperature: int
    max_tokens: int
    created_at: str
    updated_at: str


@router.get("/llm", response_model=LLMConfigResp)
async def get_llm_config(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    if not config:
        return LLMConfigResp(
            id="",
            provider="openrouter",
            model_name="gpt-4o-mini",
            temperature=7,
            max_tokens=2048,
            created_at="",
            updated_at=""
        )

    return LLMConfigResp(
        id=config.id,
        provider=config.provider,
        model_name=config.model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        created_at=str(config.created_at),
        updated_at=str(config.updated_at)
    )


@router.post("/llm", response_model=LLMConfigResp)
async def create_llm_config(
    req: LLMConfigReq,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    existing = result.scalar_one_or_none()

    config_id = existing.id if existing else str(uuid.uuid4())

    if existing:
        existing.provider = req.provider
        existing.api_key = req.api_key
        existing.base_url = req.base_url
        existing.model_name = req.model_name
        existing.temperature = req.temperature
        existing.max_tokens = req.max_tokens
    else:
        new_config = UserLLMConfig(
            id=config_id,
            user_id=current_user.id,
            provider=req.provider,
            api_key=req.api_key,
            base_url=req.base_url,
            model_name=req.model_name,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        db.add(new_config)

    await db.commit()

    return LLMConfigResp(
        id=config_id,
        provider=req.provider,
        model_name=req.model_name,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        created_at="",
        updated_at=""
    )


@router.put("/llm", response_model=LLMConfigResp)
async def update_llm_config(
    req: LLMConfigReq,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="配置不存在，请先创建")

    config.provider = req.provider
    config.api_key = req.api_key
    config.base_url = req.base_url
    config.model_name = req.model_name
    config.temperature = req.temperature
    config.max_tokens = req.max_tokens

    await db.commit()

    return LLMConfigResp(
        id=config.id,
        provider=config.provider,
        model_name=config.model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        created_at=str(config.created_at),
        updated_at=str(config.updated_at)
    )


@router.get("/llm/with-secret", response_model=LLMConfigWithSecret)
async def get_llm_config_with_secret(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    if not config:
        return LLMConfigWithSecret(
            id="",
            provider="openrouter",
            api_key=None,
            base_url=None,
            model_name="gpt-4o-mini",
            temperature=7,
            max_tokens=2048,
            created_at="",
            updated_at=""
        )

    return LLMConfigWithSecret(
        id=config.id,
        provider=config.provider,
        api_key=config.api_key,
        base_url=config.base_url,
        model_name=config.model_name,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        created_at=str(config.created_at),
        updated_at=str(config.updated_at)
    )