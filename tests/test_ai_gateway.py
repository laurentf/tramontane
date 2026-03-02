"""Unit tests for AIGateway tool-calling orchestrator."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.ai_models import AIMessage, AIResponse, MessageRole, ToolCall
from app.providers.tools.protocol import ToolContext, ToolResponse, ToolSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    content: str = "Hello!",
    tool_calls: list[ToolCall] | None = None,
    finish_reason: str = "stop",
) -> AIResponse:
    return AIResponse(
        content=content,
        model="mistral-small-latest",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        finish_reason=finish_reason,
        tool_calls=tool_calls,
    )


def _make_tool_call(
    name: str = "web_search",
    arguments: dict | None = None,
    call_id: str = "tc_1",
) -> ToolCall:
    return ToolCall(
        id=call_id,
        function_name=name,
        function_arguments=json.dumps(arguments or {"query": "test"}),
    )


def _make_llm() -> AsyncMock:
    """Create a mock LLMAdapter."""
    llm = AsyncMock()
    llm.schemas_to_tools = MagicMock(return_value=[{"type": "function"}])
    return llm


def _make_tool_registry(
    *,
    schemas: list[ToolSchema] | None = None,
    execute_result: ToolResponse | None = None,
) -> AsyncMock:
    """Create a mock ToolRegistry."""
    registry = AsyncMock()
    registry.get_all_schemas = MagicMock(
        return_value=schemas
        or [ToolSchema(name="web_search", description="Search the web", parameters={"type": "object"})]
    )
    registry.execute = AsyncMock(
        return_value=execute_result
        or ToolResponse(success=True, result="Search result: sunny weather today")
    )
    # Make __bool__ return True (non-empty registry)
    registry.__bool__ = MagicMock(return_value=True)
    registry.__len__ = MagicMock(return_value=1)
    return registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAIGatewaySingleRound:
    """Tests for single-round (no tools) behavior."""

    async def test_returns_final_text_when_no_tool_calls(self) -> None:
        from app.features.content.services.ai_gateway import run_ai_gateway

        llm = _make_llm()
        llm.generate_with_tools = AsyncMock(return_value=_make_response("Final answer"))

        registry = _make_tool_registry()
        messages = [AIMessage(role=MessageRole.USER, content="Hello")]

        result = await run_ai_gateway(llm, registry, messages)

        assert result.content == "Final answer"
        assert llm.generate_with_tools.call_count == 1

    async def test_empty_registry_calls_generate_directly(self) -> None:
        from app.features.content.services.ai_gateway import run_ai_gateway

        llm = _make_llm()
        llm.generate = AsyncMock(return_value=_make_response("Direct response"))

        # Empty registry
        registry = AsyncMock()
        registry.get_all_schemas = MagicMock(return_value=[])
        registry.__bool__ = MagicMock(return_value=False)
        registry.__len__ = MagicMock(return_value=0)

        messages = [AIMessage(role=MessageRole.USER, content="Hello")]
        result = await run_ai_gateway(llm, registry, messages)

        assert result.content == "Direct response"
        llm.generate.assert_called_once()
        llm.generate_with_tools.assert_not_called()


class TestAIGatewayMultiRound:
    """Tests for multi-round tool-calling behavior."""

    async def test_executes_tool_calls_and_feeds_results_back(self) -> None:
        from app.features.content.services.ai_gateway import run_ai_gateway

        llm = _make_llm()
        tc = _make_tool_call()

        # Round 1: LLM returns tool calls
        # Round 2: LLM returns final text
        llm.generate_with_tools = AsyncMock(
            side_effect=[
                _make_response("", tool_calls=[tc], finish_reason="tool_calls"),
                _make_response("The weather is sunny!"),
            ]
        )

        registry = _make_tool_registry()
        messages = [AIMessage(role=MessageRole.USER, content="What's the weather?")]

        result = await run_ai_gateway(llm, registry, messages)

        assert result.content == "The weather is sunny!"
        assert llm.generate_with_tools.call_count == 2
        registry.execute.assert_called_once()

    async def test_handles_tool_execution_failure(self) -> None:
        from app.features.content.services.ai_gateway import run_ai_gateway

        llm = _make_llm()
        tc = _make_tool_call()

        llm.generate_with_tools = AsyncMock(
            side_effect=[
                _make_response("", tool_calls=[tc], finish_reason="tool_calls"),
                _make_response("I could not find that information."),
            ]
        )

        registry = _make_tool_registry(
            execute_result=ToolResponse(success=False, result="API error: service unavailable")
        )
        messages = [AIMessage(role=MessageRole.USER, content="Search something")]

        result = await run_ai_gateway(llm, registry, messages)

        # Should still complete (LLM gets the error result and responds)
        assert result.content == "I could not find that information."
        registry.execute.assert_called_once()


class TestAIGatewayMaxRounds:
    """Tests for max rounds cap behavior."""

    async def test_caps_at_max_tool_rounds(self) -> None:
        from app.features.content.services.ai_gateway import MAX_TOOL_ROUNDS, run_ai_gateway

        llm = _make_llm()
        tc = _make_tool_call()

        # Every round returns tool_calls (never stops naturally)
        llm.generate_with_tools = AsyncMock(
            return_value=_make_response("", tool_calls=[tc], finish_reason="tool_calls")
        )
        # Final forced generation
        llm.generate = AsyncMock(return_value=_make_response("Forced final response"))

        registry = _make_tool_registry()
        messages = [AIMessage(role=MessageRole.USER, content="Go!")]

        result = await run_ai_gateway(llm, registry, messages)

        assert result.content == "Forced final response"
        assert llm.generate_with_tools.call_count == MAX_TOOL_ROUNDS
        llm.generate.assert_called_once()

    async def test_max_tool_rounds_is_three(self) -> None:
        from app.features.content.services.ai_gateway import MAX_TOOL_ROUNDS

        assert MAX_TOOL_ROUNDS == 3


class TestAIGatewayToolChoice:
    """Tests for tool_choice escalation (any on round 1, auto after)."""

    async def test_first_round_uses_any_tool_choice(self) -> None:
        from app.features.content.services.ai_gateway import run_ai_gateway

        llm = _make_llm()
        llm.generate_with_tools = AsyncMock(return_value=_make_response("Done"))

        registry = _make_tool_registry()
        messages = [AIMessage(role=MessageRole.USER, content="Hello")]

        await run_ai_gateway(llm, registry, messages)

        call_kwargs = llm.generate_with_tools.call_args_list[0].kwargs
        assert call_kwargs["tool_choice"] == "any"

    async def test_subsequent_rounds_use_auto_tool_choice(self) -> None:
        from app.features.content.services.ai_gateway import run_ai_gateway

        llm = _make_llm()
        tc = _make_tool_call()

        llm.generate_with_tools = AsyncMock(
            side_effect=[
                _make_response("", tool_calls=[tc], finish_reason="tool_calls"),
                _make_response("Final answer"),
            ]
        )

        registry = _make_tool_registry()
        messages = [AIMessage(role=MessageRole.USER, content="Search")]

        await run_ai_gateway(llm, registry, messages)

        round1_kwargs = llm.generate_with_tools.call_args_list[0].kwargs
        round2_kwargs = llm.generate_with_tools.call_args_list[1].kwargs
        assert round1_kwargs["tool_choice"] == "any"
        assert round2_kwargs["tool_choice"] == "auto"
