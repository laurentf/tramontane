"""Mistral Voxtral speech-to-text adapter.

Uses the /v1/audio/transcriptions API with two models:
- voxtral-mini-latest: batch transcription
- voxtral-mini-transcribe-realtime-latest: streaming
"""

import logging
from collections.abc import AsyncIterator

from mistralai import Mistral
from mistralai.models.file import File

logger = logging.getLogger(__name__)

_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/aac": "aac",
    "audio/flac": "flac",
}


def _make_file(audio_data: bytes, content_type: str | None = None) -> File:
    """Build a Mistral File object with appropriate filename and content_type."""
    ct = content_type or "audio/wav"
    ext = _CONTENT_TYPE_TO_EXT.get(ct, "wav")
    return File(file_name=f"audio.{ext}", content=audio_data, content_type=ct)


class MistralSTTAdapter:
    """Speech-to-text using Mistral Voxtral via the audio transcriptions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "voxtral-mini-latest",
        realtime_model: str = "voxtral-mini-transcribe-realtime-latest",
        timeout: float = 30.0,
    ) -> None:
        self._client = Mistral(api_key=api_key, timeout_ms=int(timeout * 1000))
        self._model = model
        self._realtime_model = realtime_model

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        language: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Transcribe audio using Voxtral batch model."""
        kwargs: dict = {
            "model": self._model,
            "file": _make_file(audio_data, content_type),
        }
        if language:
            kwargs["language"] = language

        response = await self._client.audio.transcriptions.complete_async(**kwargs)

        text = response.text or ""
        logger.debug("STT transcription (%d bytes audio): %s", len(audio_data), text[:100])
        return text.strip()

    async def transcribe_stream(
        self,
        audio_data: bytes,
        *,
        language: str | None = None,
        content_type: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream transcription using Voxtral realtime model."""
        kwargs: dict = {
            "model": self._realtime_model,
            "file": _make_file(audio_data, content_type),
        }
        if language:
            kwargs["language"] = language

        stream = await self._client.audio.transcriptions.stream_async(**kwargs)

        async for event in stream:
            if event.event == "transcription.text.delta":
                text = event.data.text
                if text:
                    yield text
            elif event.event == "transcription.done":
                break
