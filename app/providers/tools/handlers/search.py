"""Web search tool handler."""

import logging
from typing import Any

from app.providers.search.protocol import SearchAdapter
from app.providers.tools.protocol import ToolContext, ToolResponse, ToolSchema

logger = logging.getLogger(__name__)


class SearchToolHandler:
    """Tool handler for web search capabilities."""

    DEFAULT_DESCRIPTION = (
        "Search the web for current information. Use when you need "
        "up-to-date facts, news, or information beyond your training data."
    )
    DEFAULT_RESULT_INSTRUCTIONS = (
        "IMPORTANT: Use this information to answer but stay FULLY in character. "
        "Keep your usual tone, length, and style. "
        "NO markdown, NO bold, NO lists, NO long paragraphs. "
        "Answer like you normally would — short and natural."
    )

    def __init__(
        self,
        adapter: SearchAdapter,
        *,
        description: str | None = None,
        max_results: int = 5,
        result_instructions: str | None = None,
    ) -> None:
        self._adapter = adapter
        self._description = description or self.DEFAULT_DESCRIPTION
        self._max_results = max_results
        self._result_instructions = result_instructions or self.DEFAULT_RESULT_INSTRUCTIONS

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_search",
            description=self._description,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResponse:
        query = arguments.get("query", "")
        if not query:
            return ToolResponse(success=False, result="No search query provided")

        logger.info("Executing web search: %s", query)

        try:
            results = await self._adapter.search(query, max_results=self._max_results)

            if not results:
                return ToolResponse(
                    success=True,
                    result="No search results found.",
                    metadata={"query": query, "result_count": 0},
                )

            formatted = "\n".join(r.snippet for r in results)
            result_text = f"{formatted}\n\n{self._result_instructions}"

            return ToolResponse(
                success=True,
                result=result_text,
                metadata={
                    "query": query,
                    "result_count": len(results),
                    "sources": [{"title": r.title, "url": r.url} for r in results],
                },
            )

        except Exception as e:
            logger.exception("Search failed for query: %s", query)
            return ToolResponse(
                success=False,
                result=f"Search failed: {e}",
                metadata={"query": query},
            )
