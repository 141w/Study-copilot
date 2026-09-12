"""
Tests for extended classroom settings: Web Search, ASR, and Agent Mode.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import get_encryption_service
from app.db import User
from app.services import config_service
from app.services.classroom_service import build_classroom_request, sync_classroom_providers
from app.utils.auth import create_access_token


@pytest.mark.asyncio
async def test_classroom_web_search_and_asr_config_roundtrip(db_session: AsyncSession):
    """验证联网检索与 ASR 密钥的 Fernet 加密存储与掩码脱敏。"""
    user = User(
        id="user-cls-ext-1",
        username="clsext1",
        email="clsext1@test.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    get_encryption_service()

    cfg_payload = {
        "web_search_enabled": True,
        "web_search_provider": "bocha",
        "web_search_api_key": "sk-bocha-secret-1234567890",
        "web_search_base_url": "https://api.bocha.cn/v1",
        "asr_enabled": True,
        "asr_provider": "openai-whisper",
        "asr_model": "whisper-1",
        "asr_api_key": "sk-whisper-secret-9876543210",
        "asr_base_url": "https://api.openai.com/v1",
        "agent_mode": "generate",
    }

    # 保存配置
    saved = await config_service.create_or_update_llm_config(
        db=db_session,
        user=user,
        provider="openai",
        api_key="sk-main-test-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        temperature=0.7,
        max_tokens=4096,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
        classroom_config=cfg_payload,
    )

    # 1. 验证公共输出已脱敏，绝不泄露明文
    cls_out = saved["classroom_config"]
    assert cls_out["web_search_enabled"] is True
    assert cls_out["web_search_provider"] == "bocha"
    assert cls_out["has_web_search_api_key"] is True
    assert cls_out["web_search_api_key_masked"] == "sk-***7890"
    assert "web_search_api_key" not in cls_out

    assert cls_out["asr_enabled"] is True
    assert cls_out["asr_provider"] == "openai-whisper"
    assert cls_out["has_asr_api_key"] is True
    assert cls_out["asr_api_key_masked"] == "sk-***3210"
    assert "asr_api_key" not in cls_out
    assert cls_out["agent_mode"] == "generate"

    # 2. 验证服务端安全解密函数可完整还原明文
    secret_cfg = await config_service.get_llm_config_with_secret(db_session, user)
    sec_cls = secret_cfg["classroom_config"]
    assert sec_cls["web_search_api_key"] == "sk-bocha-secret-1234567890"
    assert sec_cls["asr_api_key"] == "sk-whisper-secret-9876543210"


@pytest.mark.asyncio
async def test_build_classroom_request_with_extended_settings(db_session: AsyncSession):
    """验证 build_classroom_request 自动载入用户的联网检索与智能体模式配置。"""
    user = User(
        id="user-cls-ext-2",
        username="clsext2",
        email="clsext2@test.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    await config_service.create_or_update_llm_config(
        db=db_session,
        user=user,
        provider="openai",
        api_key="sk-main-test-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        temperature=0.7,
        max_tokens=4096,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
        classroom_config={
            "web_search_enabled": True,
            "web_search_provider": "tavily",
            "web_search_api_key": "tvly-secret-12345",
            "agent_mode": "generate",
        },
    )

    req = await build_classroom_request(
        db=db_session,
        user=user,
        doc_ids=[],
        requirement="计算机网络讲解",
        enable_web_search=False,  # 用户前端未传，应自动回落为用户保存的配置
        agent_mode="default",      # 自动提升为用户配置的 generate
    )

    assert req["enableWebSearch"] is True
    assert req["webSearchProviderId"] == "tavily"
    assert req["webSearchApiKey"] == "tvly-secret-12345"
    assert req["agentMode"] == "generate"


@pytest.mark.asyncio
async def test_sync_classroom_providers_writes_yaml(db_session: AsyncSession, tmp_path):
    """验证 sync_classroom_providers 正确将 web-search 与 asr 节写入 server-providers.yml。"""
    user = User(
        id="user-cls-ext-3",
        username="clsext3",
        email="clsext3@test.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    await config_service.create_or_update_llm_config(
        db=db_session,
        user=user,
        provider="openai",
        api_key="sk-main-test-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        temperature=0.7,
        max_tokens=4096,
        embedding_model="shibing624/text2vec-base-chinese",
        embedding_dimension=768,
        classroom_config={
            "web_search_enabled": True,
            "web_search_provider": "bocha",
            "web_search_api_key": "sk-bocha-test",
            "web_search_base_url": "https://api.bocha.cn/v1",
            "asr_enabled": True,
            "asr_provider": "openai-whisper",
            "asr_model": "whisper-1",
            "asr_api_key": "sk-whisper-test",
            "asr_base_url": "https://api.openai.com/v1",
        },
    )

    import yaml

    with patch("app.services.classroom_service.os.path.abspath") as mock_abs:
        mock_abs.return_value = str(tmp_path)
        ok = await sync_classroom_providers(db_session, user)
        assert ok is True

        yaml_file = tmp_path / "server-providers.yml"
        assert yaml_file.exists()
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "web-search" in data
        assert data["web-search"]["bocha"]["apiKey"] == "sk-bocha-test"
        assert "asr" in data
        assert data["asr"]["openai-whisper"]["apiKey"] == "sk-whisper-test"
        assert data["asr"]["openai-whisper"]["models"] == ["whisper-1"]


@pytest.mark.asyncio
async def test_web_search_connectivity_helper():
    """验证 test_web_search_connectivity 函数逻辑。"""
    from app.core.web_search import test_web_search_connectivity

    # 1. 缺少 API Key 时提示
    res = await test_web_search_connectivity({
        "web_search_provider": "bocha",
        "web_search_api_key": "",
    })
    assert res["success"] is False
    assert "请填写 bocha 的 API Key" in res["message"]

    # 2. 正常连通性
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = Response(
            200,
            json={"code": 200, "data": [{"title": "test"}]},
            request=AsyncMock(),
        )
        res_ok = await test_web_search_connectivity({
            "web_search_provider": "bocha",
            "web_search_api_key": "sk-test-key",
            "web_search_base_url": "https://api.bocha.cn/v1",
        })
        assert res_ok["success"] is True
        assert "博查 AI" in res_ok["message"]


@pytest.mark.asyncio
async def test_web_search_connectivity_endpoint(client, db_session: AsyncSession):
    """验证 POST /api/config/test-web-search 端点。"""
    user = User(
        id="user-cls-ext-4",
        username="clsext4",
        email="clsext4@test.com",
        password_hash="x" * 60,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(data={"sub": user.id, "type": "access"})
    auth_headers = {"Authorization": f"Bearer {token}"}

    with patch("app.core.web_search.test_web_search_connectivity", new_callable=AsyncMock) as mock_test:
        mock_test.return_value = {
            "success": True,
            "message": "博查 AI 检索服务连接正常！(45ms)",
            "latency_ms": 45,
            "result_count": 1,
        }

        resp = await client.post(
            "/api/config/test-web-search",
            headers=auth_headers,
            json={
                "web_search_provider": "bocha",
                "web_search_api_key": "sk-test-bocha",
                "web_search_base_url": "https://api.bocha.cn/v1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "博查 AI" in data["message"]
