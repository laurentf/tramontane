"""ElevenLabs text-to-speech adapter."""

from __future__ import annotations

import re
import time

import structlog

logger = structlog.get_logger(__name__)

# Voice cache TTL in seconds (1 hour).
_VOICE_CACHE_TTL = 3600.0

# Text preparation regexes for TTS output.
_EMOJI_RE = re.compile(
    r"[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff"
    r"\U0001f1e0-\U0001f1ff\U00002702-\U000027b0\U0001f900-\U0001f9ff"
    r"\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff\U00002600-\U000026ff"
    r"\U0000fe0f\U0000200d]+",
    re.UNICODE,
)
_MD_BOLD_ITALIC_RE = re.compile(r"\*{2,3}([^*]+)\*{2,3}")
_WHITESPACE_RE = re.compile(r"[ \t]+")


class ElevenLabsTTSAdapter:
    """TTS adapter backed by the ElevenLabs API."""

    def __init__(self, api_key: str, default_model: str = "eleven_v3") -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._client = None
        self._voice_cache: list[dict] | None = None
        self._voice_cache_time: float = 0.0

        if api_key:
            from elevenlabs import AsyncElevenLabs

            self._client = AsyncElevenLabs(api_key=api_key)
        logger.info("Initialized ElevenLabsTTSAdapter with model %s", default_model)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def prepare_text(self, text: str) -> str:
        """Clean text for TTS synthesis.

        Converts *action markers* to [action] tags for ElevenLabs v3,
        strips markdown bold/italic, emojis, and collapses whitespace.
        v3 interprets [sigh], [laughs], [whispers] etc. as audio cues.
        """
        # Strip markdown bold/italic first (before single-* action conversion)
        text = _MD_BOLD_ITALIC_RE.sub(r"\1", text)
        # Convert *action* to [action] for ElevenLabs v3 audio tags
        text = re.sub(r"\*([^*]+)\*", r"[\1]", text)
        text = _EMOJI_RE.sub("", text)
        return _WHITESPACE_RE.sub(" ", text).strip()

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        *,
        model_id: str | None = None,
    ) -> bytes:
        """Synthesize speech from text.

        Returns MP3 audio bytes, or empty bytes if not configured.
        """
        if not self.is_configured:
            logger.warning("elevenlabs_not_configured", action="synthesize")
            return b""

        model_id = model_id or self._default_model

        try:
            audio_iter = self._client.text_to_speech.convert(
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
