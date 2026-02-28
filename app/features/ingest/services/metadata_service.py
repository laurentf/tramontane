"""Metadata extraction service using mutagen for ID3/Vorbis tag reading."""

from __future__ import annotations

from pathlib import Path

import structlog
from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis

from app.features.ingest.schemas.ingest import TrackMetadata, TrackTag

logger = structlog.get_logger(__name__)


def read_metadata(filepath: Path) -> TrackMetadata:
    """Read ID3/Vorbis tags from an audio file.

    Supports MP3 (EasyID3), FLAC, and OGG Vorbis. Returns a TrackMetadata
    model with graceful defaults for missing tags.
    """
    suffix = filepath.suffix.lower()
    tags: dict[str, list[str]] = {}
    duration: float | None = None

    try:
        if suffix == ".mp3":
            mp3 = MP3(filepath)
            duration = mp3.info.length if mp3.info else None
            try:
                tags = dict(EasyID3(filepath))
            except ID3NoHeaderError:
                logger.debug("no_id3_tags", path=str(filepath))
        elif suffix == ".flac":
            flac = FLAC(filepath)
            duration = flac.info.length if flac.info else None
            tags = dict(flac.tags) if flac.tags else {}
        elif suffix == ".ogg":
            ogg = OggVorbis(filepath)
            duration = ogg.info.length if ogg.info else None
            tags = dict(ogg) if ogg else {}
        else:
            logger.warning("unsupported_format_for_metadata", path=str(filepath), suffix=suffix)
    except (MutagenError, OSError, ValueError):
        logger.exception("metadata_read_error", path=str(filepath))

    # Build tags from ID3 fields
    track_tags: list[TrackTag] = []

    # Genre tags — ID3 genre can contain multiple values
    for genre in tags.get("genre", []):
        for genre_val in genre.split(";"):
            genre_val = genre_val.strip().lower()
            if genre_val:
                track_tags.append(TrackTag(tag=genre_val, category="genre", source="id3"))

    # Mood from comment or custom tags (some taggers put mood there)
    for mood in tags.get("mood", []):
        for mood_val in mood.split(";"):
            mood_val = mood_val.strip().lower()
            if mood_val:
                track_tags.append(TrackTag(tag=mood_val, category="mood", source="id3"))

    return TrackMetadata(
        title=_first_or_default(tags.get("title"), "Unknown Title"),
        artist=_first_or_default(tags.get("artist"), "Unknown Artist"),
        album=_first_or_default(tags.get("album"), None),
        duration_seconds=duration,
        file_path=str(filepath),
        tags=track_tags,
    )


def _first_or_default(values: list[str] | None, default: str | None) -> str | None:
    """Return the first value from a list, or a default."""
    if values and values[0]:
        return values[0]
    return default
