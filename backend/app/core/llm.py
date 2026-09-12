import logging

logger = logging.getLogger(__name__)

import asyncio
import random
from collections.abc import AsyncGenerator
from typing import Any, cast

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.core.tracing import record_generation

SUPPORTED_MESSAGE_FORMATS = {"openai", "anthropic", "gemini", "ollama"}


def normalize_message_format(
    messages: list[dict[str, Any]],
    fmt: str,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Normalize a list of role/content message dicts for the given API format.

    Returns a 3-tuple of:
        (format, transformed_messages, system_instruction | None)

    For ``openai`` and ``ollama`` the messages pass through unchanged and no
    system instruction is extracted. For ``anthropic`` and ``gemini`` any
    message with role ``system`` is stripped from the messages list and
    returned as a separate instruction string.
    """
    fmt = fmt if fmt in SUPPORTED_MESSAGE_FORMATS else "openai"

    if fmt in ("openai", "ollama"):
        return fmt, messages, None

    # anthropic / gemini — separate system from message array
    system_parts: list[str] = []
    filtered: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
        else:
            filtered.append(msg)

    system_instr = "\n".join(system_parts) if system_parts else None
    # Ensure at least one non-system message exists (API requirement)
    if not filtered and messages:
        filtered = [{"role": "user", "content": ""}]

    return fmt, filtered, system_instr


class LLM:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_fields: list[str] | None = None,
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
        if reasoning_fields:
            self.reasoning_fields = list(reasoning_fields)
        else:
            self.reasoning_fields = [
                f.strip()
                for f in (settings.reasoning_content_fields or "reasoning_content").split(",")
                if f.strip()
            ] or ["reasoning_content"]

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> str | None:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if resp.choices:
                    return resp.choices[0].message.content
                return None
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    logger.warning(f"Generate attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(2**attempt + random.uniform(0, 1))
                else:
                    raise
        raise last_err  # type: ignore[misc]

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
                if resp.choices:
                    content = resp.choices[0].message.content or ""
                    usage_dict = None
                    if getattr(resp, "usage", None):
                        usage_dict = {
                            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                            "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                            "total_tokens": getattr(resp.usage, "total_tokens", 0),
                        }
                    record_generation(
                        name="llm.chat",
                        model=self.model,
                        input_messages=messages,
                        output_text=content,
                        usage=usage_dict,
                    )
                    return content
                return ""
            except Exception as e:
                if attempt == max_retries - 1:
                    raise  # 最后一次重试失败，抛出异常
                logger.warning(f"Chat attempt {attempt + 1} failed: {e}. Retrying...")
                await asyncio.sleep(2**attempt + random.uniform(0, 1))  # 指数退避 + jitter
        return ""  # 不应该到达这里

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_retries: int = 1,
        include_reasoning: bool = False,
    ) -> AsyncGenerator[Any, None]:
        """流式聊天接口，逐 token 返回生成内容。支持重试（stream 创建阶段）。

        若 include_reasoning=True，返回字典流：
          {"type": "reasoning" | "token", "content": str}
        若 include_reasoning=False，返回纯字符串流（默认向后兼容）。
        """
        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            has_yielded = False
            in_think_tag = False
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=cast(Any, messages),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    # 1. Configurable reasoning fields (provider-specific delta attributes)
                    reasoning = None
                    for field_name in self.reasoning_fields:
                        val = getattr(delta, field_name, None)
                        if val:
                            reasoning = val
                            break
                        model_extra = getattr(delta, "model_extra", None)
                        if isinstance(model_extra, dict) and model_extra.get(field_name):
                            reasoning = model_extra.get(field_name)
                            break

                    if reasoning:
                        has_yielded = True
                        if include_reasoning:
                            yield {"type": "reasoning", "content": reasoning}

                    # 2. 提取 content 并做 <think> 标签容错流式解析
                    content = delta.content
                    if content:
                        has_yielded = True
                        if include_reasoning:
                            text_to_process = content
                            while text_to_process:
                                if not in_think_tag:
                                    if "<think>" in text_to_process:
                                        before, _, after = text_to_process.partition("<think>")
                                        if before:
                                            yield {"type": "token", "content": before}
                                        in_think_tag = True
                                        text_to_process = after
                                    else:
                                        yield {"type": "token", "content": text_to_process}
                                        break
                                else:
                                    if "</think>" in text_to_process:
                                        think_text, _, after = text_to_process.partition("</think>")
                                        if think_text:
                                            yield {"type": "reasoning", "content": think_text}
                                        in_think_tag = False
                                        text_to_process = after
                                    else:
                                        yield {"type": "reasoning", "content": text_to_process}
                                        break
                        else:
                            yield content
                return  # 成功完成，退出重试循环
            except Exception as e:
                if has_yielded:
                    # 已有 token 发出，重试会导致内容重复，直接抛出
                    raise
                last_err = e
                if attempt < max_retries:
                    logger.warning(f"ChatStream attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(2**attempt + random.uniform(0, 1))
                else:
                    raise
        raise last_err  # type: ignore[misc]

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Chat with function calling/tools support (OpenAI tool protocol).

        Returns a dictionary with:
        {
            "content": str | None,
            "tool_calls": list[dict],
            "finish_reason": str,
            "usage": dict | None,
        }
        """
        for attempt in range(max_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": cast(Any, messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if tools:
                    kwargs["tools"] = cast(Any, tools)

                resp = await self.client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                message = choice.message

                tool_calls_data = []
                raw_tool_calls = getattr(message, "tool_calls", None)
                if raw_tool_calls:
                    for tc in raw_tool_calls:
                        tc_func = getattr(tc, "function", None)
                        if tc_func:
                            tool_calls_data.append({
                                "id": getattr(tc, "id", ""),
                                "type": getattr(tc, "type", "function"),
                                "function": {
                                    "name": getattr(tc_func, "name", ""),
                                    "arguments": getattr(tc_func, "arguments", "{}"),
                                },
                            })

                # 原生 CoT（DeepSeek-R1 / StepFun / SiliconFlow 等）：非流式响应也可能带 reasoning_content
                reasoning_text = getattr(message, "reasoning_content", None)
                if not reasoning_text:
                    model_extra = getattr(message, "model_extra", None)
                    if isinstance(model_extra, dict):
                        reasoning_text = model_extra.get("reasoning_content")
                if not reasoning_text:
                    try:
                        raw = getattr(message, "model_dump", None)
                        if callable(raw):
                            reasoning_text = raw().get("reasoning_content")
                    except Exception:
                        reasoning_text = None

                usage_dict = None
                if getattr(resp, "usage", None):
                    usage_dict = {
                        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                        "total_tokens": getattr(resp.usage, "total_tokens", 0),
                    }

                record_generation(
                    name="llm.chat_with_tools",
                    model=self.model,
                    input_messages=messages,
                    output_text=message.content or "",
                    usage=usage_dict,
                )

                return {
                    "content": message.content,
                    "tool_calls": tool_calls_data,
                    "finish_reason": choice.finish_reason or "stop",
                    "usage": usage_dict,
                    "reasoning": reasoning_text or "",
                }
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"ChatWithTools attempt {attempt + 1} failed: {e}. Retrying...")
                await asyncio.sleep(2**attempt + random.uniform(0, 1))

        return {"content": None, "tool_calls": [], "finish_reason": "error", "usage": None, "reasoning": ""}

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "LLM":
        """从配置 dict 创建 LLM 实例（统一入口）。"""
        c = cfg or {}
        rf = c.get("reasoning_fields")
        if isinstance(rf, str):
            rf = [x.strip() for x in rf.split(",") if x.strip()]
        elif isinstance(rf, list):
            rf = [str(x) for x in rf]
        else:
            rf = None
        return cls(
            api_key=c.get("api_key"),
            base_url=c.get("base_url"),
            model=c.get("model_name") or c.get("model"),
            reasoning_fields=rf,
        )

    def format_messages(
        self,
        messages: list[dict[str, Any]],
        message_format: str = "openai",
    ) -> tuple[list[dict[str, Any]], str | None]:
        """根据目标消息格式规范化消息列表。

        对 ``openai`` / ``ollama``：直接透传。
        对 ``anthropic`` / ``gemini``：把 role=system 的消息从数组中剥离并作为
        独立 instruction/system 返回，符合对应 Provider 的 API 要求。

        返回 (normalized_messages, system_instruction | None)。
        """
        _, filtered, system_instr = normalize_message_format(messages, message_format)
        return filtered, system_instr


llm = LLM()
