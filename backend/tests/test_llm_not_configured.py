"""未配置模型凭据时的行为：构造不炸、调用给出可操作引导。

回归背景：模块级 ``llm = LLM()`` 单例会在 import 阶段要求全局 API Key，
导致全新部署（用户还没机会填自己的 Key）时进程直接起不来。
"""

from __future__ import annotations

import pytest

from app.core.llm import LLM
from app.exceptions import LLMNotConfiguredError, classify_llm_error


@pytest.fixture
def no_credentials(monkeypatch):
    """把部署级默认凭据清空，模拟"全新服务器、还没人配 Key"。"""
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(settings, "openai_base_url", "https://example.test/v1", raising=False)
    monkeypatch.setattr(settings, "openai_model", "some-model", raising=False)


def test_construction_without_key_does_not_raise(no_credentials):
    """构造阶段必须宽容——否则导入期就会拖垮整个进程。"""
    llm = LLM()
    assert llm.configured is False


def test_from_config_without_key_is_unconfigured(no_credentials):
    llm = LLM.from_config({"api_key": None, "model_name": "m"})
    assert llm.configured is False


def test_from_config_with_user_key_is_configured(no_credentials):
    llm = LLM.from_config({"api_key": "sk-user-owned", "model_name": "m"})
    assert llm.configured is True


@pytest.mark.asyncio
async def test_chat_raises_actionable_error(no_credentials):
    llm = LLM()
    with pytest.raises(LLMNotConfiguredError) as exc:
        await llm.chat([{"role": "user", "content": "hi"}])
    # 引导必须告诉用户去哪儿解决，而不是抛 SDK 的认证错误
    assert "模型设置" in exc.value.message
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_chat_stream_raises_before_yielding(no_credentials):
    llm = LLM()
    with pytest.raises(LLMNotConfiguredError):
        async for _ in llm.chat_stream([{"role": "user", "content": "hi"}]):
            pytest.fail("未配置凭据时不应产出任何 token")


@pytest.mark.asyncio
async def test_chat_with_tools_raises(no_credentials):
    llm = LLM()
    with pytest.raises(LLMNotConfiguredError):
        await llm.chat_with_tools([{"role": "user", "content": "hi"}], [])


def test_classifier_preserves_app_error_message(no_credentials):
    """分类器不得把已分类的应用异常重新包装成"AI 服务错误"。"""
    original = LLMNotConfiguredError("请先在模型设置里配置")
    result = classify_llm_error(original)
    assert result is original
    assert result.message == "请先在模型设置里配置"
