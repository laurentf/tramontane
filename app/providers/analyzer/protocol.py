"""Protocol for structured JSON analysis adapters."""

from typing import Protocol, runtime_checkable

from app.providers.ai_models import AIMessage, AIResponse


@runtime_checkable
class AnalyzerAdapter(Protocol):
    """Protocol for structured JSON analysis calls.

    JSON mode is the adapter's responsibility — callers never specify response_format.
    Uses structural subtyping — no inheritance required.
    """

    async def analyze_json(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> AIResponse: ...
