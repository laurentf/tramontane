"""Pydantic schemas for music ingest pipeline."""

from pydantic import BaseModel, Field


class TrackTag(BaseModel):
    """A single tag on a track."""

    tag: str
    category: str = Field(default="genre")
    source: str = Field(default="id3")


class TrackMetadata(BaseModel):
    """Metadata extracted from an audio file's ID3/Vorbis tags."""

    title: str = Field(default="Unknown Title")
    artist: str = Field(default="Unknown Artist")
    album: str | None = Field(default=None)
    duration_seconds: float | None = Field(default=None)
    file_path: str = Field(...)
    tags: list[TrackTag] = Field(default_factory=list)


class ScanRequest(BaseModel):
    """Request body for scanning and ingesting a music directory."""

    directory: str = Field(
        default="/music", description="Path to the directory to scan for audio files"
    )


class ScanResult(BaseModel):
    """Result of scanning a directory and writing tracks to the database."""

    scanned: int = Field(description="Number of audio files found on disk")
    stored: int = Field(description="Number of tracks upserted into the database")
    tracks: list[TrackMetadata] = Field(default_factory=list)
