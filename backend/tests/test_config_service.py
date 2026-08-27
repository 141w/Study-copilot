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


@pytest.mark.asyncio
async def test_get_llm_config_with_secret_returns_none_model_for_new_user(
    db_session: AsyncSession,
):
    """未保存过配置的用户，model_name 必须为 None（回落 .env 的 OPENAI_MODEL）。

    回归背景（2026-08-27 真机 E2E）：旧实现返回硬编码 "gpt-4o-mini"，
    使 rag_engine 走"有配置"分支、以第三方平台不存在的模型名发起调用，
    所有无配置用户的问答全部失败（供应商 code 20012）。
    """
    user = User(
        id="user-nocfg-test",
        username="nocfg",
        email="nocfg@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    result = await config_service.get_llm_config_with_secret(db_session, user)
    assert result["model_name"] is None
    assert result["api_key"] is None
