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
    """Get user's LLM config. Returns defaults if none exists.

    安全约定：永不返回明文 api_key；仅返回 has_api_key 与掩码值供前端展示。
    """
    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    config = result.scalar_one_or_none()

    if not config:
        return _default_config()

    enc = get_encryption_service()
    plaintext = enc.decrypt(config.api_key) if config.api_key else None
    return {
        **_config_to_dict(config),
        "base_url": config.base_url,
        "has_api_key": bool(config.api_key),
        "api_key_masked": mask_api_key(plaintext),
    }


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
    message_format: str | None = None,
) -> dict:
    """Create or upsert LLM config for user."""
    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    existing = result.scalar_one_or_none()

    config_id = existing.id if existing else str(uuid.uuid4())

    enc = get_encryption_service()
    # 留空 = 保持原有 Key（修复：旧实现会把空值写入从而清掉已保存的 Key，
    # 迫使前端必须把明文 Key 取回再回传，造成 /with-secret 明文出网）
    if api_key:
        stored_key = enc.encrypt(api_key)
    else:
        stored_key = existing.api_key if existing else None

    fmt = message_format or "openai"

    if existing:
        existing.provider = provider
        existing.api_key = stored_key
        existing.base_url = base_url
        existing.model_name = model_name
        existing.temperature = temperature
        existing.max_tokens = max_tokens
        existing.embedding_model = embedding_model
        existing.embedding_dimension = embedding_dimension
        existing.message_format = fmt
    else:
        new_config = UserLLMConfig(
            id=config_id,
            user_id=user.id,
            provider=provider,
            api_key=stored_key,
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            message_format=fmt,
        )
        db.add(new_config)

    await db.commit()

    return {
        "id": config_id,
        "provider": provider,
        "model_name": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "message_format": fmt,
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
    message_format: str = "openai",
) -> dict:
    """Update existing LLM config. Raises NotFoundError if none exists."""
    result = await db.execute(select(UserLLMConfig).where(UserLLMConfig.user_id == user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("配置不存在，请先创建")

    enc = get_encryption_service()
    config.provider = provider
    if api_key:
        config.api_key = enc.encrypt(api_key)
    config.base_url = base_url
    config.model_name = model_name
    config.temperature = temperature
    config.max_tokens = max_tokens
    config.embedding_model = embedding_model
    config.embedding_dimension = embedding_dimension
    config.message_format = message_format

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
        return {
            **_default_config(),
            "api_key": None,
            "base_url": None,
            # 关键（2026-08-27 真机 E2E 定位）：未保存过配置的用户不得注入
            # 硬编码 model_name——否则 chat/quiz 走"有配置"分支，
            # 用 "gpt-4o-mini" 这类第三方平台不存在的模型名覆盖 .env 里
            # 管理员校准过的 settings.openai_model，导致所有问答 20012。
            # 置 None 让 LLM 构造器回落到环境配置。
            "model_name": None,
        }

    enc = get_encryption_service()
    return {
        **_config_to_dict(config),
        "api_key": enc.decrypt(config.api_key),
        "base_url": config.base_url,
        "temperature": config.temperature,
    }


# ── helpers ────────────────────────────────────────────────────────────────


def mask_api_key(plaintext: str | None) -> str | None:
    """返回 API Key 的掩码展示值（前 3 位 + 后 4 位），永不暴露完整明文。

    例：sk-or-v1-abcdef...xyz -> sk-...xyz（短 Key 全掩码）
    """
    if not plaintext:
        return None
    if len(plaintext) <= 8:
        return "***"
    return f"{plaintext[:3]}***{plaintext[-4:]}"


def _default_config() -> dict:
    return {
        "id": "",
        "provider": "openrouter",
        "model_name": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 2048,
        "embedding_model": "shibing624/text2vec-base-chinese",
        "embedding_dimension": 768,
        "message_format": "openai",
        "base_url": None,
        "has_api_key": False,
        "api_key_masked": None,
        "created_at": "",
        "updated_at": "",
    }


def _config_to_dict(config: UserLLMConfig) -> dict:
    return {
        "id": config.id,
        "provider": config.provider,
        "model_name": config.model_name,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "embedding_model": config.embedding_model,
        "embedding_dimension": config.embedding_dimension,
        "message_format": config.message_format,
        "created_at": str(config.created_at),
        "updated_at": str(config.updated_at),
    }
