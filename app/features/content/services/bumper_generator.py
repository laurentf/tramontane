"""Station bumper generator -- one-shot LLM + TTS for idle-hour audio.

Generates short station ID phrases ("You're listening to Tramontane Radio")
via LLM, synthesizes each to MP3 via TTS, and saves them to /music/bumpers/.
These are played during idle hours with zero ongoing token cost.
"""

from pathlib import Path
from typing import Any

import structlog

from app.providers.ai_models import AIMessage, MessageRole

logger = structlog.get_logger(__name__)

# Directory for pre-recorded station bumper audio files.
BUMPERS_DIR = Path("/music/bumpers")


async def generate_bumpers(
    *,
    llm,
    tts_adapter,
    voice_id: str,
    station_name: str = "Tramontane Radio",
    count: int = 3,
) -> list[str]:
    """Generate station bumper audio files.

    Checks if bumpers already exist on disk. If so, skips generation
    (zero ongoing cost). Otherwise generates phrases via LLM and
    synthesizes each via TTS.

    Args:
        llm: LLM adapter for phrase generation.
        tts_adapter: ElevenLabsTTSAdapter for synthesis.
        voice_id: ElevenLabs voice ID.
        station_name: Name of the radio station.
        count: Number of bumper phrases to generate.

    Returns:
        List of file paths to bumper MP3 files.
    """
    # Check for existing bumpers
    existing = _get_existing_bumpers()
    if len(existing) >= count:
        logger.info(
            "bumper_generator.already_exist",
            count=len(existing),
            msg="Bumpers already generated, skipping",
        )
        return existing[:count]

    # Generate phrases via LLM
    phrases = await _generate_phrases(llm, station_name, count)
    if not phrases:
        logger.error("bumper_generator.no_phrases", msg="LLM returned no bumper phrases")
        return []

    # Ensure directory exists
    BUMPERS_DIR.mkdir(parents=True, exist_ok=True)

    # Synthesize each phrase to MP3
    file_paths: list[str] = []
    for i, phrase in enumerate(phrases[:count]):
        try:
            audio_bytes = await tts_adapter.synthesize(phrase.strip(), voice_id)
            if not audio_bytes:
                logger.warning("bumper_generator.empty_audio", phrase=phrase)
                continue

            file_path = BUMPERS_DIR / f"bumper_{i}.mp3"
            file_path.write_bytes(audio_bytes)
            file_paths.append(str(file_path))

            logger.info(
                "bumper_generator.synthesized",
                index=i,
                phrase=phrase.strip(),
                file_path=str(file_path),
            )
        except Exception:
            logger.exception("bumper_generator.synthesis_error", index=i, phrase=phrase)

    logger.info("bumper_generator.complete", generated=len(file_paths))
    return file_paths


def _get_existing_bumpers() -> list[str]:
    """Return paths of existing bumper MP3 files."""
    if not BUMPERS_DIR.exists():
        return []
    return sorted(str(p) for p in BUMPERS_DIR.glob("*.mp3"))


async def _generate_phrases(llm, station_name: str, count: int) -> list[str]:
    """Generate bumper phrases via LLM."""
    messages = [
        AIMessage(
            role=MessageRole.SYSTEM,
            content="You are a radio station announcer.",
        ),
        AIMessage(
            role=MessageRole.USER,
            content=(
                f"Generate {count} short station ID phrases (5-10 words each) "
                f"for {station_name}. Each should be a different, catchy way to say "
                f"'You're listening to {station_name}'. Return one per line."
            ),
        ),
    ]

    try:
        response = await llm.generate(messages, temperature=0.9, max_tokens=200)
        lines = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
        logger.info("bumper_generator.phrases_generated", count=len(lines))
        return lines
    except Exception:
        logger.exception("bumper_generator.phrase_generation_error")
        return []


async def generate_bumpers_task(ctx: dict[str, Any]) -> int:
    """ARQ task wrapper for bumper generation.

    Creates LLM and TTS adapters from settings and runs generate_bumpers().

    Args:
        ctx: ARQ worker context with 'pool' key.

    Returns:
        Number of bumper files generated.
    """
    from app.core.config import get_settings
    from app.providers.llm.mistral.adapter import MistralLLMAdapter
    from app.providers.speech.tts.elevenlabs.adapter import ElevenLabsTTSAdapter

    settings = get_settings()

    if not settings.mistral_api_key:
        logger.warning("bumper_task.no_llm_key", msg="Mistral API key not set, skipping bumpers")
        return 0

    if not settings.elevenlabs_api_key:
        logger.warning("bumper_task.no_tts_key", msg="ElevenLabs API key not set, skipping bumpers")
        return 0

    llm = MistralLLMAdapter(api_key=settings.mistral_api_key.get_secret_value())
    tts = ElevenLabsTTSAdapter(
        api_key=settings.elevenlabs_api_key.get_secret_value(),
        default_model=settings.tts_model,
    )

    # Use a default voice -- first available or a sensible default
    voice_id = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel" default

    paths = await generate_bumpers(
        llm=llm,
        tts_adapter=tts,
        voice_id=voice_id,
    )

    return len(paths)
