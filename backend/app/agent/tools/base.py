"""Base Tool interface and registry (absorbed from WeKnora internal/types/agent.go and tools/registry.go)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Standardized tool execution outcome."""

    success: bool
    output: str
    data: Any = None
    error: str | None = None


class Tool(ABC):
    """Abstract Base Class for Agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool function name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear description of what the tool does and when to call it."""
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON schema describing tool arguments."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool asynchronously with keyword arguments."""
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI tool/function calling definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class ToolRegistry:
    """Registry maintaining available tools with first-wins semantics against tool hijacking."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. First-registered tool wins if there are duplicates."""
        if tool.name in self._tools:
            logger.warning(
                "[ToolRegistry] Tool '%s' already registered, ignoring duplicate", tool.name
            )
            return
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]
