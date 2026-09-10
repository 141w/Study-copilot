"""Agent system prompt builder (absorbed from WeKnora agent_system_prompt.yaml)."""

from __future__ import annotations

from app.agent.tools.base import Tool


def build_agent_system_prompt(
    tools: list[Tool],
    user_envelope: str = "",
    mode: str = "deep_research",
) -> str:
    """Build the autonomous ReAct agent system prompt with active tool guidance."""
    tool_descriptions = "\n".join(
        f"- `{t.name}`: {t.description}" for t in tools
    )

    base_prompt = (
        "你是一个博学、严谨、具备自主研究能力的高级学习与知识助理（Deep Research Agent）。\n"
        "你拥有调用工具自主检索文档、翻阅段落、搜索过往对话与长期记忆的能力。\n\n"
        "### 运行原则与行为准则：\n"
        "1. **审题与规划**：针对用户的复杂问题，将其分解为子目标；按需决定先搜索文档、查阅历史还是浏览切片。\n"
        "2. **实事求是**：回答必须严格基于工具返回的客观事实。严禁凭空捏造数据、页码或概念定义。\n"
        "3. **工具协同**：\n"
        f"{tool_descriptions}\n"
        "4. **收敛与总结**：在获取充分的证据之后，停止调用工具，以条理清晰、层次分明、通俗易懂的 Markdown 格式输出最终完整解答。\n"
        "5. **引用标注**：如果从特定文档段落获得了关键事实，请在回答中明确注明来源文档或切片信息。\n"
    )

    if user_envelope:
        base_prompt = f"{base_prompt}\n\n{user_envelope}"

    return base_prompt
