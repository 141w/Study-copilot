"""
Config service — CRUD for user LLM configuration.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import get_encryption_service
from app.db import User, UserLLMConfig
from app.exceptions import NotFoundError


async def get_llm_config(
    db: AsyncSession,
    user: User,
) -> dict:
    """Get user's LLM config. Returns defaults if none exists."""
    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    config = result.scalar_one_or_none()

    if not config:
        return _default_config()

    return _config_to_dict(config)


async def create_or_update_llm_config(
    db: AsyncSession,
    user: User,
    provider: str,
    api_key: str | None,
    base_url: str | None,
    model_name: str,
    temperature: float,
    max_tokens: int,
    embedding_model: str,
    embedding_dimension: int,
) -> dict:
    """Create or upsert LLM config for user."""
    # Normalize temperature: DB stores multiplied int (7 for 0.7).
    # Accept both decimal (<=1) and already-multiplied (>1) inputs.
    normalized_temperature = float(round(temperature * 10) if temperature <= 1 else round(temperature))
    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    existing = result.scalar_one_or_none()

    config_id = existing.id if existing else str(uuid.uuid4())

    enc = get_encryption_service()
    stored_key = enc.encrypt(api_key) if api_key else api_key

    if existing:
        existing.provider = provider
        existing.api_key = stored_key
        existing.base_url = base_url
        existing.model_name = model_name
        existing.temperature = normalized_temperature
        existing.max_tokens = max_tokens
        existing.embedding_model = embedding_model
        existing.embedding_dimension = embedding_dimension
    else:
        new_config = UserLLMConfig(
            id=config_id,
            user_id=user.id,
            provider=provider,
            api_key=stored_key,
            base_url=base_url,
            model_name=model_name,
            temperature=normalized_temperature,
            max_tokens=max_tokens,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )
        db.add(new_config)

    await db.commit()

    return {
        "id": config_id,
        "provider": provider,
        "model_name": model_name,
        "temperature": normalized_temperature,
        "max_tokens": max_tokens,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "created_at": "",
        "updated_at": "",
    }


async def update_llm_config(
    db: AsyncSession,
    user: User,
    provider: str,
    api_key: str | None,
    base_url: str | None,
    model_name: str,
    temperature: float,
    max_tokens: int,
    embedding_model: str,
    embedding_dimension: int,
) -> dict:
    """Update existing LLM config. Raises NotFoundError if none exists."""
    # Normalize temperature: DB stores multiplied int (7 for 0.7).
    # Accept both decimal (<=1) and already-multiplied (>1) inputs.
    normalized_temperature = float(round(temperature * 10) if temperature <= 1 else round(temperature))

    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("配置不存在，请先创建")

    enc = get_encryption_service()
    config.provider = provider
    config.api_key = enc.encrypt(api_key) if api_key else api_key
    config.base_url = base_url
    config.model_name = model_name
    config.temperature = normalized_temperature
    config.max_tokens = max_tokens
    config.embedding_model = embedding_model
    config.embedding_dimension = embedding_dimension

    await db.commit()

    return _config_to_dict(config)


async def get_llm_config_with_secret(
    db: AsyncSession,
    user: User,
) -> dict:
    """Get user's LLM config including api_key and base_url. Returns defaults if none exists."""
    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    config = result.scalar_one_or_none()

    if not config:
        return {**_default_config(), "api_key": None, "base_url": None}

    enc = get_encryption_service()
    return {
        **_config_to_dict(config),
        "api_key": enc.decrypt(config.api_key),
        "base_url": config.base_url,
        # 数据库存的是 temperature*10（前端乘的），这里要除回来
        "temperature": config.temperature / 10,
    }


# ── helpers ────────────────────────────────────────────────────────────────


def _default_config() -> dict:
    return {
        "id": "",
        "provider": "openrouter",
        "model_name": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 2048,
        "embedding_model": "shibing624/text2vec-base-chinese",
        "embedding_dimension": 768,
        "created_at": "",
        "updated_at": "",
    }


def _config_to_dict(config: UserLLMConfig) -> dict:
    return {
        "id": config.id,
        "provider": config.provider,
        "model_name": config.model_name,
        "temperature": config.temperature / 10,
        "max_tokens": config.max_tokens,
        "embedding_model": config.embedding_model,
        "embedding_dimension": config.embedding_dimension,
        "created_at": str(config.created_at),
        "updated_at": str(config.updated_at),
    }
