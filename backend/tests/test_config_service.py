from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.services import config_service
from app.utils.auth import create_access_token


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


@pytest.mark.asyncio
async def test_test_llm_connection_success(client, db_session: AsyncSession):
    user = User(
        id="user-test-llm-1",
        username="testllm1",
        email="testllm1@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.config.LLM.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "连接成功"
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "openai",
                "api_key": "sk-mock-key-12345",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o-mini",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "连接成功" in data["reply"]


@pytest.mark.asyncio
async def test_test_llm_connection_no_key(client, db_session: AsyncSession):
    user = User(
        id="user-test-llm-2",
        username="testllm2",
        email="testllm2@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/config/test-llm",
        json={
            "provider": "openai",
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-4o-mini",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "API Key" in data["message"]


@pytest.mark.asyncio
async def test_test_llm_connection_failure(client, db_session: AsyncSession):
    user = User(
        id="user-test-llm-3",
        username="testllm3",
        email="testllm3@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.config.LLM.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = RuntimeError("Quota exceeded: 429")
        resp = await client.post(
            "/api/config/test-llm",
            json={
                "provider": "openai",
                "api_key": "sk-mock-key-12345",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o-mini",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Quota exceeded" in data["message"]


@pytest.mark.asyncio
async def test_context_window_roundtrip_and_defaults(db_session: AsyncSession):
    """Test context_window persistence and 256k default."""
    user = User(
        id="user-ctx-test",
        username="ctx_user",
        email="ctx@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    created = await config_service.create_or_update_llm_config(
        db_session,
        user,
        provider="openai",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model_name="deepseek-chat",
        temperature=0.7,
        max_tokens=4096,
        context_window=262144,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
    )
    assert created["context_window"] == 262144

    updated = await config_service.update_llm_config(
        db_session,
        user,
        provider="openai",
        api_key=None,
        base_url="https://api.openai.com/v1",
        model_name="deepseek-chat",
        temperature=0.7,
        max_tokens=4096,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
        context_window=131072,
    )
    assert updated["context_window"] == 131072

    fetched = await config_service.get_llm_config(db_session, user)
    assert fetched["context_window"] == 131072


@pytest.mark.asyncio
async def test_system_status_endpoint(client, db_session: AsyncSession):
    """Test GET /api/config/system-status returns real DB and vector engine stats."""
    user = User(
        id="user-sys-status",
        username="sys_user",
        email="sys@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/config/system-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "database" in data
    assert "document_chunks" in data["database"]
    assert data["database"]["pgvector_dimension"] == 768
    assert "vector_engine" in data
    assert data["vector_engine"]["dimension"] == 768
    assert "device" in data["vector_engine"]


@pytest.mark.asyncio
async def test_detect_llm_specs_endpoint(client, db_session: AsyncSession):
    """Test POST /api/config/detect-llm returns detected capabilities."""
    user = User(
        id="user-detect-llm",
        username="detect_user",
        email="detect@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Known vendor model (e.g. deepseek-chat -> 131072)
    resp = await client.post(
        "/api/config/detect-llm",
        json={
            "provider": "openai",
            "model_name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["context_window"] == 131072
    assert data["source"] == "vendor_spec"

    # 2. Unknown custom model fallback to 256k
    resp2 = await client.post(
        "/api/config/detect-llm",
        json={
            "provider": "openai",
            "model_name": "custom-unknown-model-xyz",
            "base_url": "https://api.custom.com/v1",
        },
        headers=headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True
    assert data2["context_window"] == 262144  # 256k default
    assert data2["source"] == "default_256k"


@pytest.mark.asyncio
async def test_classroom_config_roundtrip_and_encryption(db_session: AsyncSession):
    """验证 AI 互动课堂专属多模态配置的存储、Fernet 加密与掩码回显。"""
    user = User(
        id="user-classroom-cfg-test",
        username="cls_user",
        email="cls@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    # 1. 首次创建带有课堂图像模型配置
    cls_input = {
        "use_custom_llm": False,
        "image_enabled": True,
        "image_provider": "siliconflow",
        "image_model": "black-forest-labs/FLUX.1-schnell",
        "image_base_url": "https://api.siliconflow.cn/v1",
        "image_api_key": "sk-siliconflow-secret-12345",
        "image_size": "1024x1024",
    }
    created = await config_service.create_or_update_llm_config(
        db_session,
        user,
        provider="openai",
        api_key="sk-main-key",
        base_url="https://api.openai.com/v1",
        model_name="step-3.7-flash",
        temperature=0.7,
        max_tokens=2048,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
        classroom_config=cls_input,
    )

    cls_out = created.get("classroom_config") or {}
    assert cls_out["image_enabled"] is True
    assert cls_out["has_image_api_key"] is True
    assert cls_out["image_api_key_masked"] == "sk-***2345"
    assert "image_api_key" not in cls_out or cls_out.get("image_api_key") is None

    # 2. 内部解密服务能正确获取明文
    secret_cfg = await config_service.get_llm_config_with_secret(db_session, user)
    sec_cls = secret_cfg.get("classroom_config") or {}
    assert sec_cls["image_api_key"] == "sk-siliconflow-secret-12345"

    # 3. 更新时不传 image_api_key 应安全保留原有加密 key
    updated = await config_service.update_llm_config(
        db_session,
        user,
        provider="openai",
        api_key=None,
        base_url="https://api.openai.com/v1",
        model_name="step-3.7-flash",
        temperature=0.7,
        max_tokens=2048,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
        classroom_config={"image_enabled": True, "image_size": "1280x720"},
    )
    up_cls = updated.get("classroom_config") or {}
    assert up_cls["image_size"] == "1280x720"
    assert up_cls["has_image_api_key"] is True
    assert up_cls["image_api_key_masked"] == "sk-***2345"

    secret_cfg2 = await config_service.get_llm_config_with_secret(db_session, user)
    assert secret_cfg2["classroom_config"]["image_api_key"] == "sk-siliconflow-secret-12345"


@pytest.mark.asyncio
async def test_image_connectivity_endpoint(client, db_session: AsyncSession):
    """测试 POST /api/config/test-image 连通性测试接口。"""
    user = User(
        id="user-img-test",
        username="img_user",
        email="img@t.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    # 模拟 mock 连通性测试
    with patch("app.core.image_generator.httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        resp = await client.post(
            "/api/config/test-image",
            json={
                "image_provider": "siliconflow",
                "image_api_key": "sk-test-img",
                "image_base_url": "https://api.siliconflow.cn/v1",
                "image_model": "black-forest-labs/FLUX.1-schnell",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "图像服务连通正常" in data["message"]


