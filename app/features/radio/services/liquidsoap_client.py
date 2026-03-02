"""HTTP client for Liquidsoap Harbor API — track push operations."""

from __future__ import annotations

import httpx
import structlog

from app.core.config import get_settings
from app.features.radio.schemas.radio import PushStatus

logger = structlog.get_logger(__name__)

# Default Harbor HTTP URL (Docker service name)
LIQUIDSOAP_HARBOR_URL = "http://liquidsoap:8080"


def _get_harbor_url() -> str:
    """Get the Liquidsoap Harbor URL from settings or use the default."""
    settings = get_settings()
    return settings.liquidsoap_harbor_url or LIQUIDSOAP_HARBOR_URL


async def get_queue_status() -> dict:
    """Query Liquidsoap queue depth and current track timing.

    Returns dict with 'length' (pending tracks), 'remaining', 'elapsed', 'duration'.
    On error returns {'length': -1} so callers don't block on failure.
    """
    harbor_url = _get_harbor_url()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{harbor_url}/queue-status")
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        logger.debug("liquidsoap_queue_status_unavailable", harbor_url=harbor_url)
        return {"length": -1}
    except Exception:
        logger.warning("liquidsoap_queue_status_error", harbor_url=harbor_url)
        return {"length": -1}


async def flush_queue() -> bool:
    """Flush the Liquidsoap request queue and skip current queued track.

    Used on cold start to clear stale tracks from previous worker runs.
    Returns True on success, False on error.
    """
    harbor_url = _get_harbor_url()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{harbor_url}/flush")
            response.raise_for_status()
            logger.info("liquidsoap_queue_flushed", response=response.json())
            return True
    except Exception:
        logger.warning("liquidsoap_flush_error", harbor_url=harbor_url)
        return False


async def push_track(file_path: str) -> dict[str, str]:
    """Push a track to Liquidsoap's request queue via Harbor HTTP.

    Sends a POST request to the /push endpoint with the file path as the body.
    Returns the parsed JSON response from Liquidsoap.

    Handles connection errors gracefully — Liquidsoap may not be running
    during development.
    """
    harbor_url = _get_harbor_url()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{harbor_url}/push",
                content=file_path,
                headers={"Content-Type": "text/plain"},
            )
            response.raise_for_status()
            data = response.json()
            logger.info("track_pushed", file_path=file_path, response=data)
            return data
    except httpx.ConnectError:
        logger.warning(
            "liquidsoap_connection_error",
            harbor_url=harbor_url,
            msg="Cannot connect to Liquidsoap — is it running?",
        )
        return {"status": PushStatus.ERROR, "message": "Cannot connect to Liquidsoap"}
    except httpx.HTTPStatusError as exc:
        logger.error(
            "liquidsoap_http_error",
            harbor_url=harbor_url,
            status_code=exc.response.status_code,
        )
        msg = f"Liquidsoap returned {exc.response.status_code}"
        return {"status": PushStatus.ERROR, "message": msg}
    except httpx.HTTPError:
        logger.exception("liquidsoap_push_error", harbor_url=harbor_url)
        return {"status": PushStatus.ERROR, "message": "Failed to push track to Liquidsoap"}
    except ValueError:
        logger.exception("liquidsoap_invalid_response", harbor_url=harbor_url)
        return {"status": PushStatus.ERROR, "message": "Invalid response from Liquidsoap"}
