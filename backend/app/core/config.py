from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db, UserLLMConfig


async def get_user_llm_config(db: AsyncSession, user_id: str) -> dict:
    """获取用户的LLM配置"""
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        return None

    return {
        "provider": config.provider,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "model_name": config.model_name,
        "temperature": config.temperature / 10,
        "max_tokens": config.max_tokens
    }


class UserConfigMiddleware:
    """用户配置中间件 - 在请求中注入用户LLM配置"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, send)
