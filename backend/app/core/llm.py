from openai import AsyncOpenAI
from typing import List, Dict, Optional, AsyncGenerator
from app.config import settings
import asyncio


class LLM:
    def __init__(self, api_key=None, base_url=None, model=None):
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
            timeout=120.0,  # 2分钟超时
        )
        self.model = model or settings.openai_model

    async def generate(
        self, prompt, system_prompt=None, temperature=0.7, max_tokens=None
    ):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    async def chat(self, messages, temperature=0.7, max_tokens=None, max_retries=3):
        """带重试的聊天接口"""
        for attempt in range(max_retries):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content
            except Exception as e:
                if attempt == max_retries - 1:
                    raise  # 最后一次重试失败，抛出异常
                print(f"Chat attempt {attempt + 1} failed: {e}. Retrying...")
                await asyncio.sleep(2 ** attempt)  # 指数退避
        return ""  # 不应该到达这里

    async def chat_stream(
        self, messages, temperature=0.7, max_tokens=None
    ) -> AsyncGenerator[str, None]:
        """流式聊天接口，逐token返回生成内容"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


llm = LLM()
