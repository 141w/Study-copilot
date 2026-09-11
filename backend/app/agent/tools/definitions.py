"""The 6 foundational read-only Agent tools for Study Copilot (aligned with WeKnora agent tools)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from app.agent.tools.base import Tool, ToolResult
from app.core.rag_engine import rag_engine
from app.db import AsyncSessionLocal, Document, DocumentChunk
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


async def _load_filename_map(db, doc_ids: list[str]) -> dict[str, str]:
    """Best-effort document_id → filename map for source labels."""
    if not doc_ids:
        return {}
    try:
        res = await db.execute(
            select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
        )
        return {row[0]: row[1] for row in res.all()}
    except Exception as e:
        logger.debug("[AgentTools] filename map load failed: %s", e)
        return {}


def _chunk_to_source_entry(
    c: DocumentChunk,
    filename_map: dict[str, str] | None = None,
    relevance: float = 0.85,
) -> dict[str, Any]:
    """Normalize DocumentChunk into knowledge_search-like result shape for the source pool."""
    meta = c.chunk_metadata or {}
    page = meta.get("page", "")
    source = (filename_map or {}).get(c.document_id) or c.document_id
    return {
        "chunk": {
            "text": c.content or "",
            "document_id": c.document_id,
            "page": str(page) if page is not None else "",
            "source": source,
        },
        "relevance": relevance,
    }


class KnowledgeSearchTool(Tool):
    """Tool: knowledge_search — Semantic/hybrid retrieval over document chunks."""

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "在已选文档中执行混合语义与关键词检索，召回最相关的文档段落与知识点。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题描述"},
                "doc_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文档 ID 列表，留空表示检索所有关联文档",
                },
                "top_k": {"type": "integer", "description": "召回条数，默认 5", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        doc_ids = kwargs.get("doc_ids") or []
        top_k = kwargs.get("top_k", 5)

        try:
            results = await rag_engine.retrieve(doc_ids, query, top_k=top_k)
            if not results:
                return ToolResult(success=True, output="未检索到任何相关的文档段落。", data=[])

            lines = []
            for i, r in enumerate(results, 1):
                chunk = r.get("chunk", {})
                text_snippet = chunk.get("text", "")[:300].strip()
                page = chunk.get("page", "")
                source = chunk.get("source", "")
                lines.append(f"[{i}] 来自《{source}》(页码: {page}): {text_snippet}")

            return ToolResult(success=True, output="\n\n".join(lines), data=results)
        except Exception as e:
            logger.warning("[Tool:knowledge_search] Execution failed: %s", e)
            return ToolResult(success=False, output=f"检索失败: {e}", error=str(e))


class GrepChunksTool(Tool):
    """Tool: grep_chunks — Exact keyword substring filtering on document chunks."""

    @property
    def name(self) -> str:
        return "grep_chunks"

    @property
    def description(self) -> str:
        return "在文档段落中精准检索包含特定字词或代码片段的内容（类似于 grep / 关键词匹配）。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "待精确匹配的目标字符串或关键字"},
                "doc_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "限定的文档 ID 列表",
                },
                "limit": {"type": "integer", "description": "返回最大数量，默认 5", "default": 5},
            },
            "required": ["keyword"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        keyword = kwargs.get("keyword", "").strip()
        doc_ids = kwargs.get("doc_ids") or []
        limit = kwargs.get("limit", 5)

        if not keyword:
            return ToolResult(success=False, output="关键词不能为空", error="empty_keyword")

        try:
            async with AsyncSessionLocal() as db:
                stmt = select(DocumentChunk).where(DocumentChunk.content.ilike(f"%{keyword}%"))
                if doc_ids:
                    stmt = stmt.where(DocumentChunk.document_id.in_(doc_ids))
                stmt = stmt.limit(limit)

                res = await db.execute(stmt)
                chunks = res.scalars().all()

                if not chunks:
                    return ToolResult(success=True, output=f"未找到包含关键词 '{keyword}' 的段落。", data=[])

                filename_map = await _load_filename_map(db, list({c.document_id for c in chunks}))
                entries = [_chunk_to_source_entry(c, filename_map, relevance=0.8) for c in chunks]

                lines = []
                for i, (c, entry) in enumerate(zip(chunks, entries), 1):
                    page = (c.chunk_metadata or {}).get("page", "")
                    src = entry["chunk"]["source"]
                    lines.append(f"[{i}] 来自《{src}》(页码: {page}): {c.content[:300]}")

                return ToolResult(success=True, output="\n\n".join(lines), data=entries)
        except Exception as e:
            logger.warning("[Tool:grep_chunks] Execution failed: %s", e)
            return ToolResult(success=False, output=f"精确匹配失败: {e}", error=str(e))


class ListDocumentChunksTool(Tool):
    """Tool: list_document_chunks — Browse chunks of a specific document sequentially."""

    @property
    def name(self) -> str:
        return "list_document_chunks"

    @property
    def description(self) -> str:
        return "按序浏览或分页读取指定文档的连续切片，适合通读章节或查看上下文前后文。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "目标文档 ID"},
                "offset": {"type": "integer", "description": "切片起始偏移量，从 0 开始", "default": 0},
                "limit": {"type": "integer", "description": "读取切片数量，默认 3，最大 10", "default": 3},
            },
            "required": ["document_id"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        doc_id = kwargs.get("document_id")
        offset = kwargs.get("offset", 0)
        limit = min(kwargs.get("limit", 3), 10)

        if not doc_id:
            return ToolResult(success=False, output="文档 ID 必须提供", error="missing_doc_id")

        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == doc_id)
                    .order_by(DocumentChunk.chunk_index.asc())
                    .offset(offset)
                    .limit(limit)
                )
                res = await db.execute(stmt)
                chunks = res.scalars().all()

                if not chunks:
                    return ToolResult(success=True, output="未读取到更多文档切片。", data=[])

                filename_map = await _load_filename_map(db, list({c.document_id for c in chunks}))
                # Sequential read: relevance decays slightly by offset so later pages rank lower
                entries = [
                    _chunk_to_source_entry(c, filename_map, relevance=max(0.55, 0.9 - 0.05 * (offset + i)))
                    for i, c in enumerate(chunks)
                ]

                lines = []
                for c, entry in zip(chunks, entries):
                    page = (c.chunk_metadata or {}).get("page", "")
                    src = entry["chunk"]["source"]
                    lines.append(f"[切片 #{c.chunk_index} | 来自《{src}》 | 页码: {page}]\n{c.content}")

                return ToolResult(success=True, output="\n\n---\n\n".join(lines), data=entries)
        except Exception as e:
            logger.warning("[Tool:list_document_chunks] Failed: %s", e)
            return ToolResult(success=False, output=f"读取切片失败: {e}", error=str(e))


class GetDocumentInfoTool(Tool):
    """Tool: get_document_info — Retrieve document metadata and overview."""

    @property
    def name(self) -> str:
        return "get_document_info"

    @property
    def description(self) -> str:
        return "获取指定文档的基础元数据信息，如文件名、分块数、创建时间与处理状态。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "文档 ID"},
            },
            "required": ["document_id"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        doc_id = kwargs.get("document_id")
        if not doc_id:
            return ToolResult(success=False, output="文档 ID 必须提供", error="missing_doc_id")

        try:
            async with AsyncSessionLocal() as db:
                stmt = select(Document).where(Document.id == doc_id)
                res = await db.execute(stmt)
                doc = res.scalar_one_or_none()

                if not doc:
                    return ToolResult(success=False, output=f"未找到 ID 为 {doc_id} 的文档", error="not_found")

                info = {
                    "id": doc.id,
                    "filename": doc.filename,
                    "chunk_count": doc.chunk_count,
                    "file_size": doc.file_size,
                    "status": doc.status,
                    "created_at": str(doc.created_at),
                }
                return ToolResult(success=True, output=json.dumps(info, ensure_ascii=False, indent=2), data=info)
        except Exception as e:
            logger.warning("[Tool:get_document_info] Failed: %s", e)
            return ToolResult(success=False, output=f"获取文档信息失败: {e}", error=str(e))


class SearchConversationsTool(Tool):
    """Tool: search_conversations — Search user's past dialog history."""

    @property
    def name(self) -> str:
        return "search_conversations"

    @property
    def description(self) -> str:
        return "在用户的历史对话记录中查找相关的问答记录与讨论背景。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "想要在历史会话中查找的关键词或话题"},
                "limit": {"type": "integer", "description": "返回条数，默认 5", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        limit = kwargs.get("limit", 5)
        # Note: In agent execution context, user_id can be passed in kwargs
        user_id = kwargs.get("user_id")

        if not query:
            return ToolResult(success=False, output="查询词不能为空", error="empty_query")

        try:
            from app.db import ChatSession, Message
            async with AsyncSessionLocal() as db:
                stmt = select(Message).join(ChatSession, Message.session_id == ChatSession.id)
                if user_id:
                    stmt = stmt.where(ChatSession.user_id == user_id)
                stmt = stmt.where(Message.content.ilike(f"%{query}%")).order_by(Message.created_at.desc()).limit(limit)

                res = await db.execute(stmt)
                messages = res.scalars().all()

                if not messages:
                    return ToolResult(success=True, output="历史会话中未找到相关内容。", data=[])

                lines = []
                for m in messages:
                    role_label = "用户" if m.role == "user" else "AI"
                    lines.append(f"[{role_label}]: {m.content[:200]}")

                return ToolResult(success=True, output="\n\n".join(lines), data=[m.id for m in messages])
        except Exception as e:
            logger.warning("[Tool:search_conversations] Failed: %s", e)
            return ToolResult(success=False, output=f"搜索历史会话失败: {e}", error=str(e))


class SearchMemoryTool(Tool):
    """Tool: search_memory — Query long-term memory categories (facts, preferences, profiles)."""

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "检索用户的长期记忆库，获取用户的个人档案、学习偏好、既定事实或任务目标。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "记忆检索词"},
                "limit": {"type": "integer", "description": "返回条目数，默认 5", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        limit = kwargs.get("limit", 5)
        user_id = kwargs.get("user_id")

        if not user_id:
            return ToolResult(success=True, output="当前未绑定用户身份，无法读取长期记忆。", data=[])

        try:
            async with AsyncSessionLocal() as db:
                res = await memory_service.search(user_id=user_id, query=query, limit=limit, db=db)
                if not res.get("available", True):
                    return ToolResult(success=True, output="用户已关闭长期记忆功能。", data=[])

                items = res.get("items", [])
                if not items:
                    return ToolResult(success=True, output="长期记忆库中无匹配记录。", data=[])

                lines = [f"- [{it.kind}] {it.content}" for it in items]
                return ToolResult(success=True, output="\n".join(lines), data=[it.id for it in items])
        except Exception as e:
            logger.warning("[Tool:search_memory] Failed: %s", e)
            return ToolResult(success=False, output=f"检索长期记忆失败: {e}", error=str(e))
