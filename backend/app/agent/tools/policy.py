"""Execution policy for Agent tools (absorbed from WeKnora execution_policy.go)."""

from __future__ import annotations

# Concurrency allowlist: safe read-only tools that can execute in parallel
CONCURRENT_SAFE_TOOLS = {
    "knowledge_search",
    "grep_chunks",
    "list_document_chunks",
    "get_document_info",
    "search_conversations",
    "search_memory",
}


def can_run_concurrently(tool_name: str) -> bool:
    """Return whether the tool can run concurrently with others without side-effects."""
    return tool_name in CONCURRENT_SAFE_TOOLS
