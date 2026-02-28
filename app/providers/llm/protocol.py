"""Protocol for LLM chat completion adapters."""

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from app.providers.ai_models import AIMessage, AIResponse, StreamEvent
from app.providers.tools.protocol import ToolSchema


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocol for chat completion adapters.

    All LLM providers must implement this interface.
    Uses structural subtyping — no inheritance required.
    """

    async def generate(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        response_format: dict[str, Any] | None = None,
    ) -> AIResponse: ...

    async def stream(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]: ...

    async def stream_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[Any],
        tool_choice: str = "auto",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[StreamEvent]: ...

    async def generate_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[Any],
        tool_choice: str = "auto",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse: ...

    def schemas_to_tools(self, schemas: list[ToolSchema]) -> list[Any]: ...
