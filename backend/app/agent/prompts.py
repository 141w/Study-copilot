"""Agent system prompt builder (absorbed from WeKnora agent_system_prompt.yaml)."""

from __future__ import annotations

from app.agent.tools.base import Tool


def build_agent_system_prompt(
    tools: list[Tool],
    user_envelope: str = "",
    mode: str = "deep_research",
    documents: list[dict] | None = None,
) -> str:
    """Build the autonomous ReAct agent system prompt with active tool guidance.

    Args:
        documents: Optional list of ``{"id": ..., "filename": ...}`` for the
            user-selected research scope. Injected so the model knows which
            ``doc_ids`` to pass to knowledge tools.
    """
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
        "5. **引用标注**：凡使用文档类工具（knowledge_search / grep_chunks / list_document_chunks）得到的事实，"
        "终答中必须在对应句子末尾标注 `[来源N]`（N 与工具 observation 中给出的编号完全一致）；"
        "不得编造编号；若未检索到文档证据，则不要写 `[来源N]`，可写「未在所选文档中找到」。\n"
    )

    docs = documents or []
    if docs:
        doc_lines = "\n".join(
            f"- 《{d.get('filename') or d.get('id')}》 id=`{d.get('id')}`"
            for d in docs
        )
        doc_ids = ", ".join(f'"{d.get("id")}"' for d in docs)
        base_prompt += (
            "\n### 当前研究范围（用户已选文档）：\n"
            "回答文档相关问题时，**必须**使用 `knowledge_search` / `grep_chunks` / "
            "`list_document_chunks`，并通过 `doc_ids` 限定在下列文档内检索，"
            "禁止在范围外的文档或无文档语料上编造答案：\n"
            f"{doc_lines}\n\n"
            f"可用 doc_ids 数组（调用工具时系统会自动注入，也可显式传入）：`[{doc_ids}]`\n"
            "若检索结果为空，请如实说明在已选文档中未找到相关内容，不要改用通用知识冒充文档结论。\n"
        )
    else:
        base_prompt += (
            "\n### 当前研究范围：\n"
            "用户**尚未选择任何文档**。请优先提示用户上传/勾选文档；"
            "若用户问的是文档内容，请明确说明需要先选择文档。"
            "仅在用户明确询问通用常识时，才可不依赖文档作答。\n"
        )

    if user_envelope:
        base_prompt = f"{base_prompt}\n\n{user_envelope}"

    return base_prompt
