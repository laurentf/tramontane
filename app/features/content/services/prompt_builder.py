"""Runtime prompt assembly from host templates.

Builds complete system prompts by parameterizing template strings with host data,
appending voice format constraints, context variables, and skill prompts.
"""

import json

import structlog

from app.features.content.schemas.content import BlockContext, ContentSegmentType

logger = structlog.get_logger(__name__)

# Maps segment types to template keys in prompt_templates
_SEGMENT_TEMPLATE_KEYS: dict[ContentSegmentType, str] = {
    ContentSegmentType.GREETING: "greeting_prompt",
    ContentSegmentType.SHOW_INTRO: "show_intro_template",
    ContentSegmentType.TRACK_INTRO: "track_intro_template",
    ContentSegmentType.TRANSITION: "track_intro_template",
    ContentSegmentType.BLOCK_OPENING: "block_opening_template",
    ContentSegmentType.BLOCK_CLOSING: "block_closing_template",
}


def build_host_prompt(
    host: dict,
    template_data: dict,
    context: BlockContext,
) -> str:
    """Assemble the full system prompt for a host generation.

    Args:
        host: Host record dict (name, language, description).
        template_data: Parsed template YAML with prompt_templates key.
        context: Runtime block context (time, tracks, block brief).

    Returns:
        Complete system prompt string.
    """
    pt = template_data.get("prompt_templates", {})
    raw_desc = host.get("description", {}) or {}
    desc = json.loads(raw_desc) if isinstance(raw_desc, str) else raw_desc

    # Core identity
    core_identity_template = pt.get("core_identity_template", "")
    self_description = desc.get("self_description", "")
    if not self_description:
        self_description = pt.get("fallback_identity", "")

    system = core_identity_template.format(
        name=host.get("name", "DJ"),
        core_identity=self_description,
        language=host.get("language", "fr"),
    )

    # Voice output format
    output_format = pt.get("output_format_voice", "")
    if output_format:
        system += "\n\n" + output_format

    # Context injection
    if context.current_datetime:
        system += f"\n\nCurrent date and time: {context.current_datetime}"
    else:
        system += f"\n\nCurrent time: {context.time_of_day}"
    if context.station_location:
        system += f"\nLocation: {context.station_location}"
    system += f"\nBlock: {context.block_description}"

    if context.is_block_start:
        system += "\nThis is the start of a new block."

    if context.previous_tracks:
        system += "\nPrevious tracks played:"
        for track in context.previous_tracks:
            system += f"\n- {track}"

    return system


def get_segment_prompt(
    template_data: dict,
    segment_type: ContentSegmentType,
    *,
    track_info: dict | None = None,
    previous_track: dict | None = None,
    next_host_name: str | None = None,
    previous_host_name: str | None = None,
    context_data: list[str] | None = None,
) -> str:
    """Get the user-message prompt for a specific segment type.

    Args:
        template_data: Parsed template YAML with prompt_templates key.
        segment_type: The type of segment to generate.
        track_info: Next track metadata (title, artist) if applicable.
        previous_track: Previous track metadata (title, artist) if applicable.
        next_host_name: Name of the next host (for BLOCK_CLOSING handoff).
        previous_host_name: Name of the previous host (for BLOCK_OPENING handoff).
        context_data: Prefetched data (weather, news) to inject alongside instructions.

    Returns:
        User-message content string for segment generation.
    """
    pt = template_data.get("prompt_templates", {})
    template_key = _SEGMENT_TEMPLATE_KEYS.get(segment_type, "track_intro_template")
    prompt = pt.get(template_key, "")

    # Inject prefetched context data (weather, news) right after the template instructions
    # so the LLM sees the data co-located with the instructions that reference it.
    if context_data:
        prompt += "\n\n" + "\n\n".join(context_data)

    if track_info:
        title = track_info.get("title", "Unknown")
        artist = track_info.get("artist", "Unknown")
        prompt += f"\nNext track: {title} by {artist}"

    if previous_track:
        title = previous_track.get("title", "Unknown")
        artist = previous_track.get("artist", "Unknown")
        prompt += f"\nPrevious track: {title} by {artist}"

    if next_host_name:
        prompt += f"\nYou're handing off to {next_host_name}. Tease their show or say something friendly about them."

    if previous_host_name:
        prompt += f"\nYou're taking over from {previous_host_name}. Say something nice about them or their show."

    return prompt
