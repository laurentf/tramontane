"""Mistral AI chat completion adapter."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from mistralai import Mistral
from mistralai.models import Function
from mistralai.models import Tool as MistralTool
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.providers.ai_models import AIMessage, AIResponse, StreamEvent, ToolCall
from app.providers.mistral_utils import RETRYABLE_ERRORS, convert_message, raise_provider_error
from app.providers.tools.protocol import ToolSchema

logger = logging.getLogger(__name__)


def _extract_text(content: Any) -> str:
    """Extract text from Mistral content (str or list[TextChunk])."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    # list[TextChunk] — each chunk has a .text attribute
    return "".join(c.text for c in content if hasattr(c, "text"))


class MistralLLMAdapter:
    """Mistral AI chat completion adapter.

    Implements LLMAdapter protocol via structural subtyping.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "mistral-large-latest",
        timeout: float = 120.0,
    ) -> None:
        self._client = Mistral(api_key=api_key, timeout_ms=int(timeout * 1000))
        self._default_model = default_model
        self._timeout = timeout
        logger.info("Initialized MistralLLMAdapter with model %s", default_model)

    def schema_to_tool(self, schema: ToolSchema) -> MistralTool:
        """Convert a ToolSchema to Mistral's native tool format."""
        return MistralTool(
            function=Function(
                name=schema.name,
                description=schema.description,
                parameters=schema.parameters,
            ),
        )

    def schemas_to_tools(self, schemas: list[ToolSchema]) -> list[MistralTool]:
        """Convert multiple ToolSchemas to Mistral tools."""
        return [self.schema_to_tool(s) for s in schemas]

    @retry(
        retry=retry_if_exception_type(RETRYABLE_ERRORS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        response_format: dict[str, Any] | None = None,
    ) -> AIResponse:
        try:
            mistral_messages = [convert_message(m) for m in messages]

            api_kwargs: dict[str, Any] = {
                "model": model or self._default_model,
                "messages": mistral_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format is not None:
                api_kwargs["response_format"] = response_format

            response = await self._client.chat.complete_async(**api_kwargs)

            choice = response.choices[0]
            content = _extract_text(choice.message.content)

            return AIResponse(
                content=content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=choice.finish_reason,
            )

        except RETRYABLE_ERRORS:
            raise
        except Exception as e:
            raise_provider_error("chat", e)

    async def stream(
        self,
        messages: list[AIMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        try:
            mistral_messages = [convert_message(m) for m in messages]

            response = await self._client.chat.stream_async(
                model=model or self._default_model,
                messages=mistral_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            async for chunk in response:
                if chunk.data.choices:
                    delta = chunk.data.choices[0].delta
                    if delta.content is not None:
                        text = _extract_text(delta.content)
                        if text:
                            yield text

        except Exception as e:
            raise_provider_error("streaming", e)

    async def generate_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[MistralTool],
        tool_choice: str = "auto",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Generate completion with tool calling support (non-streaming)."""
        try:
            mistral_messages = [convert_message(m) for m in messages]

            response = await self._client.chat.complete_async(
                model=model or self._default_model,
                messages=mistral_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
            )

            choice = response.choices[0]
            content = _extract_text(choice.message.content)

            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        function_name=tc.function.name,
                        function_arguments=tc.function.arguments,
                    )
                    for tc in choice.message.tool_calls
                ]

            return AIResponse(
                content=content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
            )

        except Exception as e:
            raise_provider_error("generate_with_tools", e)

    async def stream_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[MistralTool],
        tool_choice: str = "auto",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat completion with tool calling support."""
        try:
            mistral_messages = [convert_message(m) for m in messages]

            response = await self._client.chat.stream_async(
                model=model or self._default_model,
                messages=mistral_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
            )

            pending_tool_calls: dict[int, dict[str, str]] = {}
            finish_reason: str | None = None

            async for chunk in response:
                if not chunk.data.choices:
                    continue

                choice = chunk.data.choices[0]
                delta = choice.delta

                if delta.content:
                    text = _extract_text(delta.content)
                    if text:
                        yield StreamEvent(content=text)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if hasattr(tc, "index") and tc.index is not None else 0
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": (
                                    tc.function.name if tc.function and tc.function.name else ""
                                ),
                                "arguments": (
                                    tc.function.arguments
                                    if tc.function and tc.function.arguments
                                    else ""
                                ),
                            }
                        else:
                            entry = pending_tool_calls[idx]
                            if tc.id:
                                entry["id"] = tc.id
                            if tc.function and tc.function.name:
                                entry["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                entry["arguments"] += tc.function.arguments

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            if pending_tool_calls:
                completed_calls = [
                    ToolCall(
                        id=tc_data["id"],
                        function_name=tc_data["name"],
                        function_arguments=tc_data["arguments"],
                    )
                    for tc_data in pending_tool_calls.values()
                ]
                yield StreamEvent(tool_calls=completed_calls, finish_reason=finish_reason)
            elif finish_reason:
                yield StreamEvent(finish_reason=finish_reason)

        except Exception as e:
            raise_provider_error("stream_with_tools", e)
