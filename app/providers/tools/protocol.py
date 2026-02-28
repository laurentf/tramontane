"""Protocol definitions for modular tool handlers.

Tools are capabilities that LLMs can invoke (web search, image generation, etc.).
Each tool has a handler that implements the ToolHandler protocol.
The ToolRegistry manages available tools and routes execution.
"""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ToolSchema(BaseModel):
    """Tool definition exposed to the LLM."""

    name: str = Field(..., description="Tool identifier (e.g., 'web_search')")
    description: str = Field(..., description="What this tool does")
    parameters: dict[str, Any] = Field(
        ..., description="JSON Schema for tool arguments"
    )


class ToolResponse(BaseModel):
    """Result from tool execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    result: str = Field(..., description="Text result to feed back to the LLM")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured data (e.g., image_url, source_urls)",
    )


class ToolContext(BaseModel):
    """Context passed to tool execution for channel-aware operations."""

    channel: str = Field(..., description="Channel type: 'web' | 'api'")
    host_id: str | None = Field(default=None, description="Host UUID (if applicable)")
    user_id: str | None = Field(default=None, description="User UUID")
    language: str = Field(default="fr", description="Language code")
    channel_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific metadata",
    )


@runtime_checkable
class ToolHandler(Protocol):
    """Protocol for tool handlers."""

    def get_schema(self) -> ToolSchema: ...

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResponse: ...
