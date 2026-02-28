"""Radio API endpoints — now-playing and track push."""

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import require_admin
from app.features.radio.schemas.radio import (
    NowPlaying,
    PushStatus,
    TrackPushRequest,
    TrackPushResponse,
)
from app.features.radio.services import icecast_client, liquidsoap_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/radio", tags=["radio"])


@router.get("/now-playing", response_model=NowPlaying)
async def now_playing() -> NowPlaying:
    """Get the currently playing track from Icecast.

    Returns track title, artist, genre, and listener count.
    Returns defaults if Icecast is unreachable.
    """
    return await icecast_client.get_now_playing()


@router.post("/push", response_model=TrackPushResponse)
async def push_track(
    body: TrackPushRequest,
    _user_id: str = Depends(require_admin),
) -> TrackPushResponse:
    """Push a track to the Liquidsoap playback queue.

    Validates that the file exists on disk before sending to Liquidsoap.
    """
    # Validate file exists and is within /music
    track_path = Path(body.file_path).resolve()
    if not track_path.is_relative_to(Path("/music")):
        logger.warning("push_track_path_traversal", file_path=body.file_path)
        raise ValidationError("File path outside allowed directory")
    if not track_path.is_file():
        raise NotFoundError("Track file")

    result = await liquidsoap_client.push_track(str(track_path))
    status = PushStatus(result.get("status", PushStatus.ERROR))
    message = result.get("message", "Track pushed")

    return TrackPushResponse(status=status, message=message)
