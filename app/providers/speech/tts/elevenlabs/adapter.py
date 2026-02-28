"""ElevenLabs text-to-speech adapter."""

from __future__ import annotations

import time

import structlog

logger = structlog.get_logger(__name__)

# Voice cache TTL in seconds (1 hour).
_VOICE_CACHE_TTL = 3600.0


class ElevenLabsTTSAdapter:
    """TTS adapter backed by the ElevenLabs API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None
        self._voice_cache: list[dict] | None = None
        self._voice_cache_time: float = 0.0

        if api_key:
            from elevenlabs import AsyncElevenLabs

            self._client = AsyncElevenLabs(api_key=api_key)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        *,
        model_id: str = "eleven_multilingual_v2",
    ) -> bytes:
        """Synthesize speech from text.

        Returns MP3 audio bytes, or empty bytes if not configured.
        """
        if not self.is_configured:
            logger.warning("elevenlabs_not_configured", action="synthesize")
            return b""

        try:
            audio_iter = await self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model_id,
                output_format="mp3_44100_128",
            )

            # Collect async iterator of bytes into a single buffer.
            chunks: list[bytes] = []
            async for chunk in audio_iter:
                chunks.append(chunk)

            audio = b"".join(chunks)
            logger.info("elevenlabs_synthesized", voice_id=voice_id, bytes_len=len(audio))
            return audio

        except Exception as exc:
            logger.error("elevenlabs_synthesize_error", error=str(exc))
            raise

    async def get_voices(self) -> list[dict]:
        """Fetch all available voices (cached for 1 hour).

        Returns an empty list if not configured.
        """
        if not self.is_configured:
            logger.warning("elevenlabs_not_configured", action="get_voices")
            return []

        now = time.monotonic()
        if self._voice_cache is not None and (now - self._voice_cache_time) < _VOICE_CACHE_TTL:
            return self._voice_cache

        try:
            response = await self._client.voices.get_all()
            voices: list[dict] = []
            for voice in response.voices:
                voices.append({
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "labels": dict(voice.labels) if voice.labels else {},
                    "category": getattr(voice, "category", ""),
                })

            self._voice_cache = voices
            self._voice_cache_time = now
            logger.info("elevenlabs_voices_fetched", count=len(voices))
            return voices

        except Exception as exc:
            logger.error("elevenlabs_get_voices_error", error=str(exc))
            return self._voice_cache or []

    async def resolve_voice_id(self, voice_name: str) -> str | None:
        """Resolve a voice name to its ID using case-insensitive substring match.

        Returns the voice_id or None if no match found.
        """
        voices = await self.get_voices()
        name_lower = voice_name.lower()

        # Exact match first
        for voice in voices:
            if voice["name"].lower() == name_lower:
                return voice["voice_id"]

        # Substring match
        for voice in voices:
            if name_lower in voice["name"].lower():
                return voice["voice_id"]

        logger.warning("elevenlabs_voice_not_found", voice_name=voice_name)
        return None
