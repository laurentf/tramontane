"""Transition script generator -- host speech via AIGateway.

Creates personality-consistent radio host speech scripts by combining
host personality prompts with segment-specific templates and block context.
"""

import structlog

from app.features.content.schemas.content import (
    BlockContext,
    ContentSegmentType,
    TransitionScript,
)
from app.features.content.services.ai_gateway import run_ai_gateway
from app.features.content.services.prompt_builder import (
    build_host_prompt,
    get_segment_prompt,
)
from app.providers.ai_models import AIMessage, MessageRole

logger = structlog.get_logger(__name__)

# Max tokens per segment type -- enforces CONTENT-07 character budget
_MAX_TOKENS: dict[ContentSegmentType, int] = {
    ContentSegmentType.TRACK_INTRO: 300,
    ContentSegmentType.SHOW_INTRO: 500,
    ContentSegmentType.GREETING: 400,
    ContentSegmentType.TRANSITION: 400,
    ContentSegmentType.BUMPER: 160,
    ContentSegmentType.BLOCK_OPENING: 400,
    ContentSegmentType.BLOCK_CLOSING: 240,
}

# Fallback scripts when LLM generation fails
_FALLBACK_SCRIPTS: dict[ContentSegmentType, str] = {
    ContentSegmentType.TRACK_INTRO: "And now... the next track.",
    ContentSegmentType.SHOW_INTRO: "Welcome to the show. Let's get started.",
    ContentSegmentType.GREETING: "Hey there, glad you're listening!",
    ContentSegmentType.TRANSITION: "Stay with us, more music coming up.",
    ContentSegmentType.BUMPER: "You're listening to Tramontane Radio.",
    ContentSegmentType.BLOCK_OPENING: "Hey there! Welcome, glad to be here with you.",
    ContentSegmentType.BLOCK_CLOSING: "That's it for me! Thanks for listening, see you next time.",
}


async def generate_transition(
    *,
    llm,
    tool_registry,
    host: dict,
    template_data: dict,
    context: BlockContext,
    segment_type: ContentSegmentType,
    track_info: dict | None = None,
    previous_track: dict | None = None,
    next_host_name: str | None = None,
    previous_host_name: str | None = None,
    skill_prompts: list[str] | None = None,
    model: str | None = None,
) -> TransitionScript:
    """Generate a host speech transition script.

    Uses the prompt builder to assemble system + user messages,
    then calls AIGateway for LLM generation with optional tool use.

    Args:
        llm: LLM adapter.
        tool_registry: Tool registry for AIGateway.
        host: Host record dict.
        template_data: Parsed template YAML.
        context: Runtime block context.
        segment_type: Type of segment to generate.
        track_info: Next track metadata (optional).
        previous_track: Previous track metadata (optional).
        skill_prompts: Optional skill prompt texts.
        model: Optional model override.

    Returns:
        TransitionScript with generated text.
    """
    max_tokens = _MAX_TOKENS.get(segment_type, 200)

    # Lower temperature for structured segments (openings) to improve instruction-following
    temperature = 0.5 if segment_type == ContentSegmentType.BLOCK_OPENING else 0.8

    try:
        # Weather/news data goes in the user message (not system) so it's co-located
        # with the template instructions and not buried under personality context.
        system_prompt = build_host_prompt(host, template_data, context)
        user_prompt = get_segment_prompt(
            template_data,
            segment_type,
            track_info=track_info,
            previous_track=previous_track,
            next_host_name=next_host_name,
            previous_host_name=previous_host_name,
            context_data=skill_prompts,
        )

        logger.info(
            "transition_generator.prompt",
            segment_type=segment_type,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        messages = [
            AIMessage(role=MessageRole.SYSTEM, content=system_prompt),
            AIMessage(role=MessageRole.USER, content=user_prompt),
        ]

        response = await run_ai_gateway(
            llm,
            tool_registry,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        logger.info(
            "transition_generator.generated",
            segment_type=segment_type,
            text_length=len(response.content),
            max_tokens=max_tokens,
        )

        return TransitionScript(
            text=response.content,
            segment_type=segment_type,
        )

    except Exception:
        logger.exception(
            "transition_generator.error",
            segment_type=segment_type,
            host_name=host.get("name"),
        )

        fallback = _FALLBACK_SCRIPTS.get(segment_type, "Stay tuned.")
        return TransitionScript(
            text=fallback,
            segment_type=segment_type,
        )
