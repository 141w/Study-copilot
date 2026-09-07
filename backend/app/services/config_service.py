"""
Config service — CRUD for user LLM configuration.
"""

import uuid
from typing import Any

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
    context_window: int = 262144,
    classroom_config: dict | None = None,
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
        existing_extra = existing.extra_config or {}
        existing_cls = existing_extra.get("classroom", {})
        processed_cls = _process_classroom_config(classroom_config, existing_cls, enc)
        existing.extra_config = {**existing_extra, "classroom": processed_cls}

        existing.provider = provider
        existing.api_key = stored_key
        existing.base_url = base_url
        existing.model_name = model_name
        existing.temperature = temperature
        existing.max_tokens = max_tokens
        existing.context_window = context_window
        existing.embedding_model = embedding_model
        existing.embedding_dimension = embedding_dimension
        existing.message_format = fmt
        target_config = existing
    else:
        processed_cls = _process_classroom_config(classroom_config, None, enc)
        new_config = UserLLMConfig(
            id=config_id,
            user_id=user.id,
            provider=provider,
            api_key=stored_key,
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            context_window=context_window,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            message_format=fmt,
            extra_config={"classroom": processed_cls},
        )
        db.add(new_config)
        target_config = new_config

    await db.commit()

    return _config_to_dict(target_config)


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
    context_window: int = 262144,
    classroom_config: dict | None = None,
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
    config.context_window = context_window
    config.embedding_model = embedding_model
    config.embedding_dimension = embedding_dimension
    config.message_format = message_format

    if classroom_config is not None:
        existing_extra = config.extra_config or {}
        existing_cls = existing_extra.get("classroom", {})
        processed_cls = _process_classroom_config(classroom_config, existing_cls, enc)
        config.extra_config = {**existing_extra, "classroom": processed_cls}

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
            "model_name": None,
        }

    enc = get_encryption_service()
    extra = getattr(config, "extra_config", None) or {}
    raw_cls = extra.get("classroom") or {}
    decrypted_cls = dict(raw_cls)
    if raw_cls.get("image_api_key"):
        decrypted_cls["image_api_key"] = enc.decrypt(raw_cls["image_api_key"])
    if raw_cls.get("classroom_llm_api_key"):
        decrypted_cls["classroom_llm_api_key"] = enc.decrypt(raw_cls["classroom_llm_api_key"])

    return {
        **_config_to_dict(config),
        "api_key": enc.decrypt(config.api_key),
        "base_url": config.base_url,
        "temperature": config.temperature,
        "classroom_config": decrypted_cls,
    }


# ── helpers ────────────────────────────────────────────────────────────────


def _process_classroom_config(
    raw_classroom_cfg: dict | None,
    existing_classroom_cfg: dict | None,
    enc: Any,
) -> dict:
    """处理课堂与多模态配置，对 image_api_key 和 classroom_llm_api_key 采用 Fernet 安全加密。"""
    if not raw_classroom_cfg:
        return existing_classroom_cfg or {}

    processed = dict(raw_classroom_cfg)
    existing = existing_classroom_cfg or {}

    # 处理图像 API Key 加密
    img_key = raw_classroom_cfg.get("image_api_key")
    if img_key:
        processed["image_api_key"] = enc.encrypt(img_key)
    else:
        # 留空保持已有加密密钥
        processed["image_api_key"] = existing.get("image_api_key")

    # 处理自定义课堂 LLM API Key 加密
    cls_llm_key = raw_classroom_cfg.get("classroom_llm_api_key")
    if cls_llm_key:
        processed["classroom_llm_api_key"] = enc.encrypt(cls_llm_key)
    else:
        processed["classroom_llm_api_key"] = existing.get("classroom_llm_api_key")

    return processed


def _mask_classroom_config(cfg: dict | None, enc: Any) -> dict:
    """对外暴露课堂配置，安全脱敏掩码，避免泄露明文密钥。"""
    defaults = {
        "use_custom_llm": False,
        "classroom_llm_provider": "openai",
        "classroom_llm_model": "",
        "classroom_llm_base_url": "",
        "has_classroom_llm_api_key": False,
        "classroom_llm_api_key_masked": None,
        "image_enabled": True,
        "image_provider": "siliconflow",
        "image_model": "black-forest-labs/FLUX.1-schnell",
        "image_base_url": "https://api.siliconflow.cn/v1",
        "has_image_api_key": False,
        "image_api_key_masked": None,
        "image_size": "1024x1024",
        "enable_tts": True,
        "tts_voice": "zh-CN-XiaoxiaoNeural",
        "enable_web_search": False,
    }
    if not cfg:
        return defaults

    masked = {**defaults, **cfg}
    img_enc = cfg.get("image_api_key")
    if img_enc:
        plain_img = enc.decrypt(img_enc)
        masked["has_image_api_key"] = bool(plain_img)
        masked["image_api_key_masked"] = mask_api_key(plain_img)
    else:
        masked["has_image_api_key"] = False
        masked["image_api_key_masked"] = None
    masked.pop("image_api_key", None)

    cls_llm_enc = cfg.get("classroom_llm_api_key")
    if cls_llm_enc:
        plain_cls = enc.decrypt(cls_llm_enc)
        masked["has_classroom_llm_api_key"] = bool(plain_cls)
        masked["classroom_llm_api_key_masked"] = mask_api_key(plain_cls)
    else:
        masked["has_classroom_llm_api_key"] = False
        masked["classroom_llm_api_key_masked"] = None
    masked.pop("classroom_llm_api_key", None)

    return masked


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
    enc = get_encryption_service()
    return {
        "id": "",
        "provider": "openrouter",
        "model_name": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 2048,
        "context_window": 262144,
        "embedding_model": "shibing624/text2vec-base-chinese",
        "embedding_dimension": 768,
        "message_format": "openai",
        "base_url": None,
        "has_api_key": False,
        "api_key_masked": None,
        "classroom_config": _mask_classroom_config(None, enc),
        "created_at": "",
        "updated_at": "",
    }


def _config_to_dict(config: UserLLMConfig) -> dict:
    enc = get_encryption_service()
    extra = getattr(config, "extra_config", None) or {}
    classroom_cfg = _mask_classroom_config(extra.get("classroom"), enc)
    return {
        "id": config.id,
        "provider": config.provider,
        "model_name": config.model_name,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "context_window": getattr(config, "context_window", 262144),
        "embedding_model": config.embedding_model,
        "embedding_dimension": config.embedding_dimension,
        "message_format": config.message_format,
        "classroom_config": classroom_cfg,
        "created_at": str(config.created_at),
        "updated_at": str(config.updated_at),
    }
