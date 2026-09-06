"""
Course Generator — 基于文档内容自动生成课程大纲 + 测验。

使用已有的 LLM + QuizGenerator + Transformations 能力，
不引入新依赖。

流程：
  1. 拼装文档上下文（从 DocumentChunk 读取）
  2. LLM 生成课程大纲（JSON：标题 + 章节列表）
  3. 每章节生成测验题（复用 QuizGenerator）
  4. 返回结构化课程数据（前端或 service 层负责创建 CourseSpace）
"""

import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLM
from app.core.quiz_generator import quiz_generator
from app.db import Document, DocumentChunk, User

logger = logging.getLogger(__name__)

# ── 文档上下文提取 ────────────────────────────────────────────────────────────


def _build_context_from_chunks(chunks: list[dict], max_chars: int = 8000) -> str:
    """从文档块拼装 LLM 可消费的上下文文本。"""
    parts: list[str] = []
    total = 0
    for c in chunks:
        text = c.get("content", "").strip()
        if not text:
            continue
        sep_len = 2 if parts else 0
        if total + sep_len + len(text) > max_chars:
            remaining = max_chars - total - sep_len
            if remaining <= 0:
                break
            parts.append(text[:remaining])
            break
        parts.append(text)
        total += sep_len + len(text)
    return "\n\n".join(parts)


async def _load_document_context(
    db: AsyncSession, doc_ids: list[str], user_id: str, max_chars: int = 8000
) -> str:
    """从多个文档加载文本上下文，校验文档归属当前用户。"""
    if not doc_ids:
        return ""
    result = await db.execute(
        select(DocumentChunk.content, DocumentChunk.document_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.document_id.in_(doc_ids),
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    rows = result.all()
    return _build_context_from_chunks(
        [{"content": r[0], "document_id": r[1]} for r in rows],
        max_chars=max_chars,
    )


# ── 课程大纲生成 ─────────────────────────────────────────────────────────────


OUTLINE_PROMPT_PREFIX = """你是一位课程设计专家。请根据提供的文档内容，生成一份结构化的课程大纲。

要求：
1. 课程标题要具体、有吸引力
2. 包含 3-6 个章节，每章有明确的学习目标
3. 每章包含 2-4 个关键知识点
4. 难度标注：入门 / 进阶 / 深入

返回 JSON 格式（不要其他文字）：
{
  "title": "课程标题",
  "description": "课程简介（1-2句话）",
  "difficulty": "入门",
  "sections": [
    {
      "id": "s1",
      "title": "章节标题",
      "objective": "本章学习目标",
      "difficulty": "入门",
      "key_points": ["知识点1", "知识点2"]
    }
  ]
}"""


async def generate_outline(
    context: str,
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调用 LLM 生成课程大纲。"""
    llm = LLM.from_config(llm_config)
    prompt = f"{OUTLINE_PROMPT_PREFIX}\n\n文档内容：\n{context[:6000]}"

    try:
        raw = await llm.generate(
            prompt,
            system_prompt="你是课程设计专家。只返回 JSON，不要其他文字。",
            temperature=0.5,
            max_tokens=2048,
        )
        if raw:
            # 清理 Markdown 代码块标记
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()
            match = re.search(r"\{[\s\S]+\}", cleaned)
            if match:
                return json.loads(match.group())
    except Exception as e:
        logger.error("Failed to generate outline: %s", e)

    # Fallback
    return {
        "title": "未命名课程",
        "description": "基于文档自动生成的课程",
        "difficulty": "入门",
        "sections": [
            {
                "id": f"s{i}",
                "title": f"第 {i+1} 部分",
                "objective": "学习核心概念",
                "difficulty": "入门",
                "key_points": ["要点"],
            }
            for i in range(3)
        ],
    }


# ── 综合生成 ─────────────────────────────────────────────────────────────────


async def generate_course(
    db: AsyncSession,
    user: User,
    doc_ids: list[str],
    requirement: str = "",
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """完整的课程生成流程。

    参数
    ----
    doc_ids : list[str]
        源文档 ID（需属于该 user）。
    requirement : str
        用户对课程主题/风格的要求（可选）。
    llm_config : dict | None
        LLM 配置，None 则使用用户的默认配置。

    返回
    ----
    { outline, quizzes }  — 结构化课程数据，前端负责展示和创建 CourseSpace。
    """
    # 1. 加载文档上下文（仅限当前用户的非删除文档）
    context = await _load_document_context(db, doc_ids, user.id, max_chars=8000)
    if not context:
        context = f"用户要求：{requirement}" if requirement else "（无文档内容）"

    # 2. 用户要求注入
    if requirement:
        context = f"用户课程要求：{requirement}\n\n文档内容：\n{context}"

    # 3. 生成大纲
    outline = await generate_outline(context, llm_config)

    # 4. 为每个章节生成测验
    quizzes: list[dict[str, Any]] = []
    for section in outline.get("sections", [])[:5]:  # 最多 5 个章节
        title = section.get("title", "")
        sec_id = section.get("id", str(uuid.uuid4()))
        key_points = section.get("key_points", [])
        section_context = f"{title}: {', '.join(key_points)}\n\n{context[:3000]}"
        section_quizzes = await quiz_generator.generate_quizzes(
            section_context, choice_count=2, short_answer_count=1
        )
        for q in section_quizzes:
            q["section_id"] = sec_id
            q["section_title"] = title
        quizzes.extend(section_quizzes)

    logger.info(
        "Course generated: %d sections, %d quizzes",
        len(outline.get("sections", [])),
        len(quizzes),
    )

    return {
        "outline": outline,
        "quizzes": quizzes,
        "source_doc_ids": doc_ids,
    }
