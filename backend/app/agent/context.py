"""Agent token estimation and context compaction (absorbed from WeKnora compactor.go & estimator.go)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.llm import LLM

logger = logging.getLogger(__name__)

# Fallback token estimate: ~1.5 tokens per Chinese char / 4 chars per English word
PER_MESSAGE_OVERHEAD = 4


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Fast approximation of total tokens in messages list without external heavy dependency."""
    total = 0
    for m in messages:
        total += PER_MESSAGE_OVERHEAD
        content = m.get("content")
        if isinstance(content, str):
            total += int(len(content) * 0.8) + 1
        tool_calls = m.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                func = tc.get("function", {})
                total += int(len(func.get("arguments", "")) * 0.5) + 10
    return total


def trim_history(
    history: list[dict[str, Any]] | None,
    *,
    max_messages: int = 10,
    max_tokens: int = 2000,
) -> list[dict[str, Any]]:
    """Keep the newest history under both message-count and token budgets.

    Walks backwards from the end; drops older turns first. Always keeps the
    most recent non-empty message when history is non-empty, even if that
    single turn exceeds ``max_tokens`` (caller still gets the latest context).
    """
    if not history:
        return []
    window = history[-max_messages:] if max_messages > 0 else list(history)
    selected: list[dict[str, Any]] = []
    used = 0
    for msg in reversed(window):
        cost = estimate_tokens([msg])
        if selected and used + cost > max_tokens:
            break
        selected.append(msg)
        used += cost
    selected.reverse()
    return selected


class ContextCompactor:
    """Monitors context window usage and performs selective compaction when exceeding thresholds."""

    def __init__(
        self,
        max_context_tokens: int = 16000,
        keep_recent_messages: int = 4,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.keep_recent_messages = keep_recent_messages

    async def maybe_compact(
        self,
        messages: list[dict[str, Any]],
        llm: LLM,
    ) -> list[dict[str, Any]]:
        """If messages exceed max_context_tokens, summarize older messages preserving KeepRecent window."""
        current_tokens = estimate_tokens(messages)
        if current_tokens <= self.max_context_tokens or len(messages) <= (self.keep_recent_messages + 2):
            return messages

        logger.info(
            "[AgentCompactor] Triggering context compaction (%d estimated tokens > %d threshold)",
            current_tokens,
            self.max_context_tokens,
        )

        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        non_system = messages[1:] if system_msg else messages

        if len(non_system) <= self.keep_recent_messages:
            return messages

        to_summarize = non_system[:-self.keep_recent_messages]
        keep_recent = non_system[-self.keep_recent_messages:]

        summary_text = "\n".join(
            f"{m.get('role')}: {str(m.get('content', ''))[:150]}" for m in to_summarize
        )

        try:
            prompt = (
                "请将以下前期研究与工具调用历史浓缩为一段清晰简明的事实摘要（不超过200字），保留核心发现与结论：\n\n"
                f"{summary_text}\n\n摘要："
            )
            summary = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=250,
            )
            compacted: list[dict[str, Any]] = []
            if system_msg:
                compacted.append(system_msg)
            compacted.append({
                "role": "system",
                "content": f"【前期研究与执行摘要】：{summary}",
            })
            compacted.extend(keep_recent)
            return compacted
        except Exception as e:
            logger.warning("[AgentCompactor] Compaction LLM call failed: %s, using truncation", e)
            result = []
            if system_msg:
                result.append(system_msg)
            result.extend(keep_recent)
            return result
