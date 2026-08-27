import logging

logger = logging.getLogger(__name__)

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, cast

import httpx
from openai import AsyncOpenAI

from app.config import settings


class LLM:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        # 创建不使用代理的 httpx 客户端（避免 VPN 劫持）
        http_client = httpx.AsyncClient(
            proxy=None,
            transport=httpx.AsyncHTTPTransport(proxy=None),
        )
        # connect 显式设短：VPN/TUN 黑洞环境下直连会长时间无响应，
        # 必须尽快失败进入重试/降级；read 保持宽裕以容纳长生成。
        # cast 说明：openai 2.x 对 timeout/http_client 使用其内嵌 httpx 类型别名，
        # 与外部标准 httpx 对象在运行时完全兼容，仅静态命名空间不同。
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
            timeout=cast(Any, httpx.Timeout(connect=8.0, read=120.0, write=30.0, pool=10.0)),
            http_client=cast(Any, http_client),
        )
        self.model = model or settings.openai_model

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str | None:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # cast：dict 形式消息是 OpenAI API 官方支持的 payload，SDK 的 TypedDict
        # 参数类型对 dict[str, str] 过窄，运行时完全兼容
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_retries: int = 3,
    ) -> str:
        """带重试的聊天接口"""
        for attempt in range(max_retries):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                # SDK 的 content 可为 None（模型空回复）；chat 契约是非空 str
                content = resp.choices[0].message.content
                return content if content is not None else ""
            except Exception as e:
                if attempt == max_retries - 1:
                    raise  # 最后一次重试失败，抛出异常
                logger.warning(f"Chat attempt {attempt + 1} failed: {e}. Retrying...")
                await asyncio.sleep(2**attempt)  # 指数退避
        return ""  # 不应该到达这里

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天接口，逐token返回生成内容"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


llm = LLM()
