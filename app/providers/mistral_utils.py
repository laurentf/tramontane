"""Shared utilities for Mistral AI adapters (LLM, Embedding, Analyzer, STT)."""

import logging
from typing import Any, NoReturn, NotRequired, TypedDict

import httpx

from app.providers.ai_exceptions import AIProviderError, RateLimitError
from app.providers.ai_models import AIMessage

logger = logging.getLogger(__name__)

# Transient errors that should be retried (superset across all adapters)
RETRYABLE_ERRORS = (TimeoutError, httpx.TimeoutException, ConnectionError, OSError, RateLimitError)


class MistralMessage(TypedDict):
    """Dict format accepted by the Mistral SDK chat endpoints."""

    role: str
    content: str | None
    tool_call_id: NotRequired[str]
    name: NotRequired[str]
    tool_calls: NotRequired[list[dict[str, Any]]]


def raise_for_rate_limit(exc: Exception) -> None:
    """Raise RateLimitError if the exception looks like a 429."""
    error_str = str(exc).lower()
    if "429" in error_str or "rate_limit" in error_str or "rate limit" in error_str:
        logger.warning("Mistral rate limit hit: %s", exc)
        raise RateLimitError(provider="mistral") from exc


def convert_message(msg: AIMessage) -> MistralMessage:
    """Convert an AIMessage to the dict format expected by the Mistral SDK."""
    if msg.role == "tool":
        return MistralMessage(
            role="tool",
            content=msg.content,
            tool_call_id=msg.tool_call_id,
            name=msg.name,
        )

    if msg.role == "assistant" and msg.tool_calls:
        return MistralMessage(
            role="assistant",
            content=msg.content if msg.content else None,
            tool_calls=[
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function_name,
                        "arguments": tc.function_arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        )

    return MistralMessage(role=msg.role, content=msg.content)


def raise_provider_error(operation: str, exc: Exception) -> NoReturn:
    """Check for rate limit, then raise AIProviderError."""
    raise_for_rate_limit(exc)
    logger.error("Mistral %s error: %s", operation, exc)
    raise AIProviderError(provider="mistral", message=str(exc)) from exc
