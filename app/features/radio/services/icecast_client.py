"""HTTP client for Icecast server — now-playing and statistics."""

from __future__ import annotations

import html

import httpx
import structlog

from app.core.config import get_settings
from app.features.radio.schemas.radio import NowPlaying

logger = structlog.get_logger(__name__)

# Default Icecast URL (Docker service name)
ICECAST_URL = "http://icecast:8000"


def _get_icecast_url() -> str:
    """Get the Icecast URL from settings or use the default."""
    settings = get_settings()
    return settings.icecast_url or ICECAST_URL


async def get_now_playing() -> NowPlaying:
    """Fetch the current now-playing info from Icecast's status-json endpoint.

    Parses the icestats.source list for the /stream.mp3 mount and extracts
    the StreamTitle (format: "Artist - Title"), splitting on the first " - ".

    Returns a NowPlaying model with defaults if Icecast is unreachable or
    the stream is not active.
    """
    icecast_url = _get_icecast_url()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{icecast_url}/status-json.xsl")
            response.raise_for_status()
            data = response.json()

        # Icecast returns sources as either a single dict or a list
        sources = data.get("icestats", {}).get("source", [])
        if isinstance(sources, dict):
            sources = [sources]

        # Find the /stream.mp3 mount
        for source in sources:
            listen_url = source.get("listenurl", "")
            if "/stream.mp3" in listen_url:
                # Parse StreamTitle: "Artist - Title"
                stream_title = source.get("title") or source.get("yp_currently_playing", "")
                title, artist = _parse_stream_title(stream_title)
                listeners = source.get("listeners", 0)
                try:
                    listeners = int(listeners)
                except (ValueError, TypeError):
                    listeners = 0

                return NowPlaying(
                    title=title,
                    artist=artist,
                    album_art=None,  # Album art resolved separately via track DB lookup
                    genre=source.get("genre"),
                    listeners=listeners,
                )

        # Stream mount not found — stream may not be active
        logger.info("icecast_mount_not_found", msg="/stream.mp3 mount not active")
        return NowPlaying()

    except httpx.ConnectError:
        logger.warning(
            "icecast_connection_error",
            icecast_url=icecast_url,
            msg="Cannot connect to Icecast — is it running?",
        )
        return NowPlaying()
    except httpx.HTTPError:
        logger.warning("icecast_status_error", icecast_url=icecast_url)
        return NowPlaying()
    except Exception:
        logger.exception("icecast_unexpected_error", icecast_url=icecast_url)
        return NowPlaying()


def _parse_stream_title(stream_title: str) -> tuple[str, str]:
    """Parse an ICY StreamTitle string into (title, artist).

    Format is typically "Artist - Title". Splits on the first occurrence
    of " - " to handle titles or artists that contain hyphens.

    Returns ("Unknown Track", "Unknown Artist") if the input is empty.
    """
    if not stream_title or not stream_title.strip():
        return ("Unknown Track", "Unknown Artist")

    # Icecast returns HTML-escaped strings (e.g. &amp; for &)
    stream_title = html.unescape(stream_title)

    # Split on first " - " only
    parts = stream_title.split(" - ", 1)
    if len(parts) == 2:
        artist = parts[0].strip() or "Unknown Artist"
        title = parts[1].strip() or "Unknown Track"
        return (title, artist)

    # No separator — treat the whole string as the title
    return (stream_title.strip(), "Unknown Artist")
