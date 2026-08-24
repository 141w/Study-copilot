import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.services import config_service


@pytest.mark.asyncio
async def test_temperature_roundtrip_is_backend_owned(db_session: AsyncSession):
    """Frontend now sends decimal temperature directly.
    Backend must normalize/store/read-back consistently without frontend help."""
    user = User(
        id="user-temp-test",
        username="temp",
        email="t@t.com",
        password_hash="x" * 60,  # NOT NULL 约束；本测试不涉及登录
    )
    db_session.add(user)
    await db_session.commit()

    await config_service.create_or_update_llm_config(
        db_session,
        user,
        provider="openrouter",
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
        model_name="openai/gpt-4o-mini",
        temperature=0.7,
        max_tokens=2048,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
    )

    fetched = await config_service.get_llm_config(db_session, user)
    assert fetched["temperature"] == 0.7
    assert fetched["model_name"] == "openai/gpt-4o-mini"
