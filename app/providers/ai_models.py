"""Shared data models for AI providers (LLM + embedding).

All AI-related data structures use Pydantic BaseModel for validation.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Tool call requested by the model during generation."""

    id: str = Field(..., description="Unique tool call identifier")
    function_name: str = Field(..., description="Name of the function to call")
    function_arguments: str = Field(..., description="JSON-encoded function arguments")

    model_config = {"frozen": True}


class StreamEvent(BaseModel):
    """Single event from a tool-aware streaming response."""

    content: str | None = Field(default=None, description="Content chunk (if any)")
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Completed tool calls (if any)"
    )
    finish_reason: str | None = Field(
        default=None, description="Why generation stopped (stop, tool_calls, etc.)"
    )


class MessageRole(StrEnum):
    """Valid roles for AI chat messages."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class StatusKey(StrEnum):
    """Known status keys for SSE streaming indicators."""

    THINKING = "thinking"
    TYPING = "typing"
    SEARCHING = "searching"
    GENERATING_IMAGE = "generating_image"
    CHECKING_WEATHER = "checking_weather"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class StatusEvent:
    """Lightweight status indicator for SSE streaming."""

    status: StatusKey


class AIMessage(BaseModel):
    """Single message for AI adapter calls.

    Used by all chat adapters (Mistral, etc.) as the transport format.
    """

    role: MessageRole = Field(..., description="Message role: user, assistant, system, or tool")
    content: str = Field(..., description="Message content")
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Tool calls made by assistant (role=assistant only)"
    )
    tool_call_id: str | None = Field(
        default=None, description="ID of the tool call this message responds to (role=tool only)"
    )
    name: str | None = Field(
        default=None, description="Tool name for tool result messages (role=tool only)"
    )

    model_config = {"frozen": True}


class ToolResult(BaseModel):
    """Result of an executed tool call, for storage/context."""

    tool_name: str = Field(..., description="Name of the tool (e.g., 'web_search')")
    query: str = Field(..., description="The query/arguments passed to the tool")
    result: str = Field(..., description="The tool's result text")


class AIResponse(BaseModel):
    """Response from a chat completion request.

    Returned by LLMAdapter.generate().
    """

    content: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model name used")
    usage: dict[str, int] = Field(
        ..., description="Token usage (prompt_tokens, completion_tokens, total_tokens)"
    )
    finish_reason: str | None = Field(
        default=None, description="Why generation stopped (stop, length, tool_calls, etc.)"
    )
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Tool calls requested by the model (if any)"
    )
    tool_results: list[ToolResult] | None = Field(
        default=None, description="Executed tool results (for storage/context)"
    )


class EmbeddingResponse(BaseModel):
    """Response from an embedding generation request."""

    embeddings: list[list[float]] = Field(..., description="List of embedding vectors")
    model: str = Field(..., description="Model name used")
    usage: dict[str, int] = Field(..., description="Token usage")
    dimensions: int = Field(..., description="Embedding vector dimensions")
