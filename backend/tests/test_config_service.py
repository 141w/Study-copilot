import pytest
from app.db import User
from app.services import config_service
from sqlalchemy.ext.asyncio import AsyncSession


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

    created = await config_service.create_or_update_llm_config(
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

    # 写入响应必须与 GET 一致：返回十进制温度，而非存储原值（7）
    assert created["temperature"] == 0.7

    updated = await config_service.update_llm_config(
        db_session,
        user,
        provider="openrouter",
        api_key=None,
        base_url="https://openrouter.ai/api/v1",
        model_name="openai/gpt-4o-mini",
        temperature=0.5,
        max_tokens=2048,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
    )
    assert updated["temperature"] == 0.5

    fetched = await config_service.get_llm_config(db_session, user)
    assert fetched["temperature"] == 0.5
    assert fetched["model_name"] == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_temperature_legacy_multiplied_form_still_accepted(db_session: AsyncSession):
    """旧双形态兼容：>1 的输入视为已乘 10 的存储值，读回时仍 /10。"""
    user = User(
        id="user-temp-legacy",
        username="temp-legacy",
        email="t2@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    created = await config_service.create_or_update_llm_config(
        db_session,
        user,
        provider="openai",
        api_key="sk-test",
        base_url=None,
        model_name="gpt-4o-mini",
        temperature=7,  # 旧客户端形态：实际温度 0.7
        max_tokens=2048,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
    )
    # 响应统一为十进制语义
    assert created["temperature"] == pytest.approx(0.7)

    fetched = await config_service.get_llm_config(db_session, user)
    assert fetched["temperature"] == pytest.approx(0.7)
