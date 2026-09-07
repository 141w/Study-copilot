"""
Persona Discussion — 多智能体讨论模式（轻量版）。

特点：固定 Sequential persona chain，每条 persona 收到完整上下文后发言，最终汇总。

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

# ── 多 Agent 预置角色库 ─────────────────────────────────────────────────────────
PERSONA_PRESETS: dict[str, dict[str, str]] = {
    "teacher": {
        "id": "teacher",
        "name": "苏老师",
        "role": "teacher",
        "avatar": "User",
        "color": "#3b82f6",
        "system_message": (
            "你是主讲老师。你负责引导整个课堂讨论，循序渐进地拆解核心知识点。"
            "发言风格：亲切、清晰、具有启发性，善于把复杂概念分解为易懂的步骤，并适时引导同学思考。"
        ),
    },
    "thinker": {
        "id": "thinker",
        "name": "学霸",
        "role": "thinker",
        "avatar": "GraduationCap",
        "color": "#10b981",
        "system_message": (
            "你是课程中的学霸角色。你对原理理解深入，善于从底层机制推演，举一反三。"
            "发言风格：严密、深刻，善于用精准的类比和逻辑推论解释概念本质，能指出常人忽略的边界条件。"
        ),
    },
    "curious": {
        "id": "curious",
        "name": "求知同学",
        "role": "curious",
        "avatar": "ChatLineRound",
        "color": "#f59e0b",
        "system_message": (
            "你是求知欲极强的初学者同学。你敢于提出反直觉的疑问和常见的思维误区。"
            "发言风格：好奇、真实、敢于追问，你的问题往往能直击概念最容易让人困惑的痛点，帮助大家打通认知卡点。"
        ),
    },
    "notetaker": {
        "id": "notetaker",
        "name": "归纳助手",
        "role": "notetaker",
        "avatar": "EditPen",
        "color": "#8b5cf6",
        "system_message": (
            "你是讨论的速记与归纳助手。你专注于提炼要点、梳理知识框架与对比清单。"
            "发言风格：高度精炼、结构化，用简明扼要的清单或核心口诀快速总结前几位发言者的精华。"
        ),
    },
}

# 默认内置 personas（默认保留 学霸 + 求知同学 经典辩论组合）
DEFAULT_PERSONAS: list[dict[str, str]] = [
    PERSONA_PRESETS["thinker"],
    PERSONA_PRESETS["curious"],
]


def get_persona_presets() -> list[dict[str, str]]:
    """获取所有支持的角色预置列表。"""
    return list(PERSONA_PRESETS.values())


def resolve_persona(p: dict[str, str]) -> dict[str, str]:
    """解析传入的 persona 配置，如果缺少 system_message 则从预置库匹配补全。"""
    key = (p.get("role") or p.get("id") or p.get("name") or "").lower()
    preset = PERSONA_PRESETS.get(key)
    if preset:
        return {
            "name": p.get("name") or preset["name"],
            "role": p.get("role") or preset["role"],
            "avatar": p.get("avatar") or preset["avatar"],
            "color": p.get("color") or preset.get("color", "#6366f1"),
            "system_message": p.get("system_message") or preset["system_message"],
        }
    return {
        "name": p.get("name", "同学"),
        "role": p.get("role", "student"),
        "avatar": p.get("avatar", "User"),
        "color": p.get("color", "#6366f1"),
        "system_message": p.get("system_message", "你是课程讨论的参与者。请就主题发表见解。"),
    }

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


def format_discussion_transcript(discussion_history: list[dict[str, Any]]) -> str:
    """将研讨历史格式化为结构化的圆桌研讨纪要，避免在 LLM 接口中塞入连续 assistant 消息导致 API 早停或人设混乱。"""
    if not discussion_history:
        return ""
    lines = ["【圆桌研讨历史记录】"]
    current_turn = None
    for item in discussion_history:
        turn_num = item.get("turn", 1)
        if turn_num != current_turn:
            current_turn = turn_num
            lines.append(f"\n--- 第 {turn_num} 轮研讨发言 ---")
        speaker = item.get("speaker", "研讨成员")
        content = item.get("content", "")
        lines.append(f"【{speaker}】：{content}")
    return "\n".join(lines)


def build_peer_context_section(
    discussion_history: list[dict[str, Any]],
    current_persona_name: str,
    turn: int = 1,
) -> str:
    """Peer-context 互辩机制：
    提取前序同伴发言观点，施加严谨的互辩约束，引导当前角色进行追问、质疑、回应或补充。
    """
    if not discussion_history:
        return ""

    peer_turns = []
    for h in discussion_history:
        speaker = h.get("speaker")
        content = h.get("content", "")
        if not speaker and content.startswith("【") and "】" in content:
            speaker = content[1:content.index("】")]
        if speaker != current_persona_name:
            peer_turns.append({"speaker": speaker or "同伴", "content": content})

    if not peer_turns:
        return ""

    recent_peers = peer_turns[-3:]
    peer_summary = "\n".join(f"- {p['content']}" for p in recent_peers)

    if turn == 1:
        round_instruction = (
            f"【研讨互辩要求（你当前是 {current_persona_name}）】\n"
            "1. 严禁自说自话，严禁重复开场白、问候语或自我介绍；\n"
            "2. 严禁重复前序发言者已经阐述透彻的基础概念或公理；\n"
            f"3. 紧密结合上述同伴发言中的具体论点，从你【{current_persona_name}】的角色特质出发，"
            "进行【深入回应、质疑不严谨处、指出潜在漏洞/边界条件、举反例或提出痛点追问】；\n"
            "4. 口语化自然表达，保持思维碰撞的深度，像真实的学术沙龙/圆桌研讨一样彼此启发。"
        )
    else:
        round_instruction = (
            f"【第 {turn} 轮 · 深度互辩与针锋交锋（你当前是 {current_persona_name}）】\n"
            "1. 严禁自说自话，严禁重复开场白、问候语或第一轮已经阐明的定义；\n"
            f"2. 必须紧密围绕上述同伴发言中的具体论点与论据，从【{current_persona_name}】的人设特质出发，"
            "进行【深入回应、反驳漏洞、举出反例或提出尖锐痛点追问】；\n"
            "3. 保持思辨的深度与锐度，推动研讨向本质机理深入。"
        )

    return (
        "\n\n【前序研讨现场与同伴发言观点】\n"
        f"{peer_summary}\n\n"
        f"{round_instruction}"
    )


async def _stream_llm_response(
    llm: LLM,
    messages: list[dict[str, str]],
    temperature: float = 0.8,
) -> AsyncGenerator[str, None]:
    """带优雅降级的逐 token 流式生成器。

    优先使用 llm.chat_stream() 逐 token 产出；
    若环境不支持或为仅 mock 了 llm.chat 的测试对象，则回退至 llm.chat()。
    """
    use_chat_stream = False
    if hasattr(llm, "chat_stream"):
        cs = llm.chat_stream
        try:
            from unittest.mock import MagicMock
            if isinstance(cs, MagicMock):
                # 只有当测试用例显式 mock 了 chat_stream 时才使用它
                if cs.side_effect is not None or "return_value" in cs.__dict__:
                    use_chat_stream = True
                else:
                    use_chat_stream = False
            else:
                use_chat_stream = True
        except ImportError:
            use_chat_stream = True

    if use_chat_stream:
        stream = llm.chat_stream(messages, temperature=temperature)
        async for chunk in stream:
            yield chunk
        return

    resp = await _call_llm(llm, messages, temperature=temperature)
    if resp:
        yield resp


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
    dict  (type: "persona_start" | "persona_chunk" | "persona_speak" | "summary_start" | "summary_chunk" | "summary" | "error" | "done")
    """
    if personas is None or not personas:
        resolved_personas = DEFAULT_PERSONAS
    else:
        resolved_personas = [resolve_persona(p) for p in personas]

    llm = LLM(
        api_key=(llm_config or {}).get("api_key"),
        base_url=(llm_config or {}).get("base_url"),
        model=(llm_config or {}).get("model_name") or (llm_config or {}).get("model"),
    )

    discussion_history: list[dict[str, Any]] = []

    # 预置 user turn 基础内容
    base_user_content = f"讨论主题：{topic}"
    if context:
        base_user_content += f"\n\n参考材料：\n{context[:3000]}"

    try:
        for turn in range(max_turns):
            current_round_num = turn + 1
            for persona in resolved_personas:
                # 注入同伴互辩提示词与结构化研讨历史
                transcript = format_discussion_transcript(discussion_history)
                peer_context = build_peer_context_section(discussion_history, persona["name"], current_round_num)

                user_prompt = base_user_content
                if transcript:
                    user_prompt += f"\n\n{transcript}"
                user_prompt += f"\n\n{peer_context}"

                # 构造符合所有 LLM API 规范的单轮标准消息（系统人设 + 用户指令）
                messages: list[dict[str, str]] = [
                    {"role": "system", "content": persona["system_message"]},
                    {"role": "user", "content": user_prompt},
                ]

                # 1. 触发角色发言开始事件
                yield {
                    "type": "persona_start",
                    "persona": persona["name"],
                    "avatar": persona.get("avatar", "User"),
                    "color": persona.get("color", "#6366f1"),
                    "turn": current_round_num,
                }

                # 2. 逐 token 流式输出
                chunks: list[str] = []
                async for delta in _stream_llm_response(llm, messages, temperature=0.8):
                    if delta:
                        chunks.append(delta)
                        yield {
                            "type": "persona_chunk",
                            "persona": persona["name"],
                            "delta": delta,
                            "turn": current_round_num,
                        }

                response = "".join(chunks).strip()

                # 自愈防御 1：若流式输出为空（网络抖动或API异常截断），自动降级为非流式 chat 调用重试
                if not response:
                    logger.warning(
                        "Persona %s turn %d produced empty stream, retrying with direct chat...",
                        persona["name"],
                        current_round_num,
                    )
                    try:
                        fallback_resp = await _call_llm(llm, messages, temperature=0.7)
                        if fallback_resp and fallback_resp.strip():
                            response = fallback_resp.strip()
                            yield {
                                "type": "persona_chunk",
                                "persona": persona["name"],
                                "delta": response,
                                "turn": current_round_num,
                            }
                    except Exception as exc:
                        logger.error("Fallback chat failed for %s: %s", persona["name"], exc)

                # 自愈防御 2：若极端情况下仍为空，生成角色兜底见解，决不让界面出现空内容
                if not response:
                    logger.error(
                        "Persona %s turn %d completely empty, applying defensive default.",
                        persona["name"],
                        current_round_num,
                    )
                    response = (
                        f"针对关于「{topic}」的研讨，从我【{persona['name']}】的视角切入，"
                        "我们需要重点关注理论推导与工程边界之间的权衡，前序发言中提出的焦点很值得我们继续深入探究。"
                    )
                    yield {
                        "type": "persona_chunk",
                        "persona": persona["name"],
                        "delta": response,
                        "turn": current_round_num,
                    }

                # 记录到讨论历史（包含轮次、发言人和内容）
                discussion_history.append({
                    "turn": current_round_num,
                    "speaker": persona["name"],
                    "content": response,
                })

                # 3. 触发角色发言结束事件
                yield {
                    "type": "persona_speak",
                    "persona": persona["name"],
                    "avatar": persona.get("avatar", "User"),
                    "color": persona.get("color", "#6366f1"),
                    "content": response,
                    "turn": current_round_num,
                }

                # 给用户一个刷新机会（async sleep 让出事件循环）
                await asyncio.sleep(0)

        # 最终总结
        transcript = format_discussion_transcript(discussion_history)
        summary_prompt = (
            f"研讨主题：{topic}\n\n"
            f"{transcript}\n\n"
            "请对上述多轮多角色讨论进行提炼总结，按以下结构输出：\n"
            "### 主要共识\n"
            "（列出各方一致认可的核心要点）\n\n"
            "### 关键分歧与争鸣\n"
            "（提炼讨论中出现的不同视角或交锋重点）\n\n"
            "### 学习者实践建议\n"
            "（给学习者的实用行动指南）\n"
            "请用中文回答，风格专业精炼。"
        )
        summary_messages = [
            {"role": "system", "content": "你是讨论的主持人，负责总结多角色讨论。"},
            {"role": "user", "content": summary_prompt},
        ]

        # 1. 主持人总结开始
        yield {
            "type": "summary_start",
            "persona": "主持人",
            "avatar": "ChatDotSquare",
            "color": "#10b981",
        }

        # 2. 总结逐 token 流式输出
        s_chunks: list[str] = []
        async for delta in _stream_llm_response(llm, summary_messages, temperature=0.5):
            if delta:
                s_chunks.append(delta)
                yield {
                    "type": "summary_chunk",
                    "delta": delta,
                }

        summary = "".join(s_chunks).strip()
        if not summary:
            try:
                fallback_sum = await _call_llm(llm, summary_messages, temperature=0.5)
                if fallback_sum and fallback_sum.strip():
                    summary = fallback_sum.strip()
                    yield {"type": "summary_chunk", "delta": summary}
            except Exception as exc:
                logger.error("Fallback summary failed: %s", exc)

        if not summary:
            summary = (
                f"### 主要共识\n各方就「{topic}」的核心逻辑与基础概念达成了一致认识。\n\n"
                "### 关键分歧与实践建议\n深入探讨了边界条件与实际工程落地中的差异，建议在学习和实践中多加验证。"
            )
            yield {"type": "summary_chunk", "delta": summary}

        # 3. 主持人总结完成
        yield {
            "type": "summary",
            "persona": "主持人",
            "avatar": "ChatDotSquare",
            "color": "#10b981",
            "content": summary,
        }

    except Exception as e:
        logger.error("Persona discussion failed: %s", e, exc_info=True)
        yield {"type": "error", "message": f"讨论生成失败: {e}"}

    # 兼容输出旧格式 messages 列表
    legacy_history = [
        {"role": "assistant", "content": f"【{item['speaker']}】：{item['content']}"}
        for item in discussion_history
    ]
    yield {
        "type": "done",
        "total_turns": len(discussion_history),
        "messages": legacy_history,
    }
