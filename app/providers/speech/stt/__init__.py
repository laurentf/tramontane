"""Speech-to-text provider protocol."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class STTProvider(Protocol):
    """Speech-to-text provider interface."""

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        language: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Transcribe audio buffer to text."""
        ...
