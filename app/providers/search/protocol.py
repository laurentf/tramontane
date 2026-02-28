"""Protocol definitions for web search adapters."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Single search result from a web search query."""

    title: str = Field(..., description="Page title")
    url: str = Field(..., description="Page URL")
    snippet: str = Field(..., description="Text snippet/description")
    score: float | None = Field(default=None, description="Relevance score (if available)")


@runtime_checkable
class SearchAdapter(Protocol):
    """Protocol for web search adapters."""

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchResult]: ...
