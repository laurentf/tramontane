"""Pydantic schemas for radio API endpoints."""

from pydantic import BaseModel, Field


class NowPlaying(BaseModel):
    """Current now-playing information from Icecast."""

    title: str = Field(default="Unknown Track", description="Current track title")
    artist: str = Field(default="Unknown Artist", description="Current track artist")
    album_art: str | None = Field(default=None, description="Album art URL or path")
    genre: str | None = Field(default=None, description="Track genre")
    listeners: int = Field(default=0, description="Current listener count")


class TrackPushRequest(BaseModel):
    """Request to push a track to the Liquidsoap queue."""

    file_path: str = Field(..., description="Absolute path to the audio file on the server")


class TrackPushResponse(BaseModel):
    """Response from pushing a track to Liquidsoap."""

    status: str = Field(..., description="Status of the push operation (ok, error)")
    message: str = Field(..., description="Descriptive message about the result")
