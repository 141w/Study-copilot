"""
Persona Discussion — 多智能体讨论模式（轻量版）。

与 OpenMAIC 的 Director Graph 区别：固定 Sequential persona chain，
不做动态编排。每条 persona 收到完整上下文后发言，最终汇总。

使用方式：
    from app.core.persona_discussion import persona_discussion

    async for event in persona_discussion.discuss(
        topic="什么是向量空间?",
        personas=[
            {"name": "学霸", "system_message": "你是数学学霸..."},
            {"name": "初学者", "system_message": "你是刚学线代的学生..."},
        ],
        context="可选的参考文档内容",
        llm_config={"api_key": "...", "model": "..."},
    ):
        print(event)  # {type: "persona_speak", persona: "学霸", content: "..."}
                      # {type: "done", messages: [...]}
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.core.llm import LLM

logger = logging.getLogger(__name__)

# 默认内置 personas（若前端未传入自定义 persona）
DEFAULT_PERSONAS: list[dict[str, str]] = [
    {
        "name": "学霸",
        "avatar": "🎓",
        "system_message": (
            "你是课程中的学霸角色。你理解深入，能举一反三。"
            "发言风格：清晰、有条理，善于用类比和例子解释概念。"
            "给出独到的见解，但不要说教。"
        ),
    },
    {
        "name": "初学者",
        "avatar": "🌱",
        "system_message": (
            "你是课程中的初学者角色。你对概念有基本理解，但总有一些困惑。"
            "发言风格：真诚、好奇，会提出常见的疑问和误解。"
            "你的问题往往代表了大多数学生的真实困惑。"
        ),
    },
]

_MAX_RETRIES = 2


async def _call_llm(
    llm: LLM,
    messages: list[dict[str, str]],
    temperature: float = 0.8,
) -> str:
    """带重试的单次 LLM 调用。"""
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return await llm.chat(
                messages=messages,
                temperature=temperature,
                max_retries=1,
            )
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRIES - 1:
                logger.warning("Persona LLM attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(2**attempt)
    raise last_err  # type: ignore[misc]


async def discuss(
    topic: str,
    personas: list[dict[str, str]] | None = None,
    context: str = "",
    llm_config: dict[str, Any] | None = None,
    max_turns: int = 2,
) -> AsyncGenerator[dict[str, Any], None]:
    """多智能体讨论流。

    Parameters
    ----------
    topic : str
        讨论主题（用户的原始问题）。
    personas : list[dict] | None
        [{"name", "avatar", "system_message"}, ...]
        默认使用内置的 学霸 + 初学者。
    context : str
        可选：参考文档内容（RAG 检索结果）。
    llm_config : dict | None
        LLM 配置 {api_key, base_url, model}。
    max_turns : int
        每对 persona 之间最多讨论几轮。

    Yields
    ------
    dict  (type: "persona_speak" | "summary" | "error" | "done")
    """
    if personas is None or not personas:
        personas = DEFAULT_PERSONAS

    llm = LLM(
        api_key=(llm_config or {}).get("api_key"),
        base_url=(llm_config or {}).get("base_url"),
        model=(llm_config or {}).get("model"),
    )

    discussion_history: list[dict[str, str]] = []

    # 预置 user turn
    user_turn = {"role": "user", "content": f"讨论主题：{topic}"}
    if context:
        user_turn["content"] += f"\n\n参考材料：\n{context[:3000]}"

    try:
        for turn in range(max_turns):
            for persona in personas:
                # 构造消息列表：系统 persona + 讨论历史
                messages: list[dict[str, str]] = [
                    {"role": "system", "content": persona["system_message"]},
                ]
                # 只带最近的对话历史（避免过长）
                history_slice = discussion_history[-6:] if discussion_history else []
                messages.extend(history_slice)
                messages.append(user_turn)

                response = await _call_llm(llm, messages)

                # 记录到讨论历史
                discussion_history.append({"role": "assistant", "content": response})

                yield {
                    "type": "persona_speak",
                    "persona": persona["name"],
                    "avatar": persona.get("avatar", "💬"),
                    "content": response,
                    "turn": turn + 1,
                }

                # 给用户一个刷新机会（async sleep 让出事件循环）
                await asyncio.sleep(0)

        # 最终总结
        summary_prompt = (
            f"请对上述关于「{topic}」的多角色讨论做一个简洁总结："
            "列出主要共识、关键分歧、以及给学习者的建议。用中文回答。"
        )
        summary_messages = [
            {"role": "system", "content": "你是讨论的主持人，负责总结多角色讨论。"},
            *discussion_history[-8:],
            {"role": "user", "content": summary_prompt},
        ]
        summary = await _call_llm(llm, summary_messages, temperature=0.5)

        yield {
            "type": "summary",
            "persona": "主持人",
            "avatar": "📋",
            "content": summary,
        }

    except Exception as e:
        logger.error("Persona discussion failed: %s", e, exc_info=True)
        yield {"type": "error", "message": f"讨论生成失败: {e}"}

    yield {
        "type": "done",
        "total_turns": len(discussion_history),
        "messages": discussion_history,
    }
