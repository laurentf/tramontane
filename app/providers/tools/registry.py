"""Tool registry for managing and executing LLM tools."""

import logging
from typing import Any

from app.providers.tools.protocol import (
    ToolContext,
    ToolHandler,
    ToolResponse,
    ToolSchema,
)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for tool handlers.

    Usage:
        registry = ToolRegistry()
        registry.register(SearchToolHandler(tavily_adapter))
        schemas = registry.get_all_schemas()
        response = await registry.execute("web_search", {"query": "..."})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, handler: ToolHandler) -> None:
        schema = handler.get_schema()
        self._handlers[schema.name] = handler
        logger.info("Registered tool: %s", schema.name)

    def get_all_schemas(self) -> list[ToolSchema]:
        return [h.get_schema() for h in self._handlers.values()]

    def get_schema(self, tool_name: str) -> ToolSchema | None:
        handler = self._handlers.get(tool_name)
        return handler.get_schema() if handler else None

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResponse:
        handler = self._handlers.get(tool_name)
        if not handler:
            logger.warning("Unknown tool requested: %s", tool_name)
            return ToolResponse(
                success=False,
                result=f"Unknown tool: {tool_name}",
            )

        try:
            logger.info("Executing tool: %s", tool_name)
            return await handler.execute(arguments, context)
        except Exception as e:
            logger.exception("Tool execution failed: %s", tool_name)
            return ToolResponse(
                success=False,
                result=f"Tool execution failed: {e}",
            )

    def clone(self) -> "ToolRegistry":
        """Create a shallow copy with the same handlers registered."""
        new = ToolRegistry()
        new._handlers = dict(self._handlers)
        return new

    @property
    def available_tools(self) -> list[str]:
        return list(self._handlers.keys())

    def __len__(self) -> int:
        return len(self._handlers)

    def __bool__(self) -> bool:
        return len(self._handlers) > 0
