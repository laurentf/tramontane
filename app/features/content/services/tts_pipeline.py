"""TTS pipeline -- ElevenLabs synthesis + file write + Liquidsoap push.

Converts text scripts to audio via the ElevenLabs TTS adapter, writes MP3
files to the generated audio directory, and pushes them to Liquidsoap's
request queue for on-air playback.
"""

from pathlib import Path

import structlog

from app.features.radio.services.liquidsoap_client import push_track

logger = structlog.get_logger(__name__)

# Directory for generated TTS audio files.
# /music/generated/ is within /music/, so Liquidsoap's push_handler
# validation (path must start with /music/) already works.
GENERATED_DIR = Path("/music/generated")


async def synthesize_and_push(
    *,
    tts_adapter,
    text: str,
    voice_id: str,
    segment_id: str,
) -> str | None:
    """Synthesize text to speech and push audio to Liquidsoap.

    Args:
        tts_adapter: ElevenLabsTTSAdapter instance.
        text: Script text to synthesize.
        voice_id: ElevenLabs voice ID.
        segment_id: Unique segment identifier (used for filename).

    Returns:
        File path of the generated MP3, or None on failure.
    """
    if not tts_adapter.is_configured:
        logger.warning("tts_pipeline.not_configured", msg="TTS adapter not configured, skipping")
        return None

    try:
        text = tts_adapter.prepare_text(text)
        audio_bytes = await tts_adapter.synthesize(text, voice_id)

        if not audio_bytes:
            logger.error("tts_pipeline.empty_audio", segment_id=segment_id)
            return None

        # Ensure directory exists
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        file_path = GENERATED_DIR / f"{segment_id}.mp3"
        file_path.write_bytes(audio_bytes)

        logger.info(
            "tts_pipeline.written",
            segment_id=segment_id,
            file_path=str(file_path),
            bytes_len=len(audio_bytes),
        )

        # Push to Liquidsoap queue
        await push_track(str(file_path))

        logger.info("tts_pipeline.pushed", file_path=str(file_path))
        return str(file_path)

    except Exception:
        logger.exception("tts_pipeline.error", segment_id=segment_id)
        return None


async def push_music_track(file_path: str) -> bool:
    """Push a music track to Liquidsoap's queue.

    Simple wrapper around push_track that returns True/False for success.

    Args:
        file_path: Path to the audio file (must start with /music/).

    Returns:
        True if push succeeded, False otherwise.
    """
    try:
        result = await push_track(file_path)
        logger.info("tts_pipeline.music_pushed", file_path=file_path, result=result)
        return True
    except Exception:
        logger.exception("tts_pipeline.music_push_error", file_path=file_path)
        return False
