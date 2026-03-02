"""Content generation schemas.

Defines the data contracts for content segments, music selections,
transition scripts, and block context used throughout the content pipeline.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ContentSegmentType(StrEnum):
    """Types of content segments in a radio block."""

    TRACK_INTRO = "TRACK_INTRO"
    SHOW_INTRO = "SHOW_INTRO"
    GREETING = "GREETING"
    TRANSITION = "TRANSITION"
    BUMPER = "BUMPER"
    BLOCK_OPENING = "BLOCK_OPENING"
    BLOCK_CLOSING = "BLOCK_CLOSING"


class MusicSelection(BaseModel):
    """A track selected by the LLM for playback."""

    track_id: str = Field(..., description="UUID of the selected track")
    title: str = Field(..., description="Track title")
    artist: str = Field(..., description="Track artist")
    file_path: str = Field(..., description="Path to the audio file")
    reason: str = Field(..., description="LLM reasoning for picking this track")
    duration_seconds: float | None = Field(default=None, description="Track duration in seconds")


class TransitionScript(BaseModel):
    """A text script for host speech (transition, intro, greeting, etc.)."""

    text: str = Field(..., description="The script text for TTS synthesis")
    segment_type: ContentSegmentType = Field(..., description="Type of segment")
    estimated_duration_seconds: float | None = Field(
        default=None, description="Estimated speech duration in seconds"
    )


class ContentSegment(BaseModel):
    """A single segment in a radio block (speech, music, or both)."""

    segment_id: str = Field(..., description="UUID for this segment")
    block_id: str = Field(..., description="UUID of the parent schedule block")
    host_id: str = Field(..., description="UUID of the host")
    segment_type: ContentSegmentType = Field(..., description="Type of segment")
    script: TransitionScript | None = Field(
        default=None, description="Speech script (if segment has host speech)"
    )
    track: MusicSelection | None = Field(
        default=None, description="Music selection (if segment has a track)"
    )
    audio_path: str | None = Field(
        default=None, description="Path to generated TTS audio file"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the segment was created"
    )


class BlockContext(BaseModel):
    """Runtime context injected into prompts for a schedule block."""

    time_of_day: str = Field(..., description="Current time description (e.g., 'evening', 'morning')")
    block_description: str = Field(..., description="Block brief / creative direction")
    previous_tracks: list[str] = Field(
        default_factory=list, description="Recently played track descriptions"
    )
    is_block_start: bool = Field(
        default=False, description="Whether this is the first segment of the block"
    )
    host_language: str = Field(
        default="fr", description="Host's on-air language code"
    )
    current_datetime: str = Field(
        default="", description="Formatted current date/time (e.g. 'samedi 1 mars 2026, 16h30')"
    )
    station_location: str = Field(
        default="", description="Station location (e.g. 'Montpellier, France')"
    )
