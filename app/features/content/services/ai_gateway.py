"""AIGateway orchestrator -- multi-turn tool-calling loop.

Central nervous system for all content generation. Manages the LLM -> tools ->
LLM cycle until the model produces a final text response or the round cap is hit.
"""

import json

import structlog

from app.providers.ai_models import AIMessage, AIResponse, MessageRole
from app.providers.tools.protocol import ToolContext
from app.providers.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)

MAX_TOOL_ROUNDS = 3


async def run_ai_gateway(
    llm,  # LLMAdapter (protocol, not imported to avoid circular)
    tool_registry: ToolRegistry,
    messages: list[AIMessage],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
    tool_context: ToolContext | None = None,
) -> AIResponse:
    """Execute LLM generation with an optional tool-calling loop.

    If tool_registry has no tools, calls llm.generate() directly (no loop).
    Otherwise, loops up to MAX_TOOL_ROUNDS: on each round the LLM may return
    tool_calls which are executed and fed back. After exhausting rounds,
    a final generation without tools is forced.
    """
    schemas = tool_registry.get_all_schemas()

    # No tools available -- skip the tool loop entirely
    if not schemas:
        logger.info("ai_gateway.no_tools", msg="No tools registered, calling generate directly")
        return await llm.generate(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )

    tools = llm.schemas_to_tools(schemas)
    logger.info(
        "ai_gateway.tools_available",
        tool_count=len(tools),
        tool_names=[s.name for s in schemas],
    )

    for round_num in range(MAX_TOOL_ROUNDS):
        # Force tool use on round 1 so the model actually calls its tools
        choice = "any" if round_num == 0 else "auto"
        logger.info(
            "ai_gateway.round",
            round=round_num + 1,
            max_rounds=MAX_TOOL_ROUNDS,
            tool_choice=choice,
        )

        response = await llm.generate_with_tools(
            messages,
            tools=tools,
            tool_choice=choice,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.tool_calls:
            logger.info("ai_gateway.final_response", round=round_num + 1)
            return response

        # Append assistant message with tool_calls to conversation
        messages.append(
            AIMessage(
                role=MessageRole.ASSISTANT,
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
        )

        # Execute each tool call and append results
        for tc in response.tool_calls:
            try:
                args = json.loads(tc.function_arguments)
            except json.JSONDecodeError:
                logger.warning(
                    "ai_gateway.bad_tool_args",
                    tool=tc.function_name,
                    raw=tc.function_arguments,
                )
                args = {}

            logger.info(
                "ai_gateway.tool_execute",
                tool=tc.function_name,
                round=round_num + 1,
            )

            result = await tool_registry.execute(
                tc.function_name, args, tool_context
            )

            messages.append(
                AIMessage(
                    role=MessageRole.TOOL,
                    content=result.result,
                    tool_call_id=tc.id,
                    name=tc.function_name,
                )
            )

            logger.info(
                "ai_gateway.tool_result",
                tool=tc.function_name,
                success=result.success,
            )

    # Exhausted all rounds -- force final generation without tools
    logger.warning(
        "ai_gateway.max_rounds_exhausted",
        max_rounds=MAX_TOOL_ROUNDS,
        msg="Forcing final generation without tools",
    )
    return await llm.generate(
        messages, model=model, temperature=temperature, max_tokens=max_tokens
    )
