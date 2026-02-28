"""HTTP client for Liquidsoap Harbor API — track push operations."""

from __future__ import annotations

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Default Harbor HTTP URL (Docker service name)
LIQUIDSOAP_HARBOR_URL = "http://liquidsoap:8080"


def _get_harbor_url() -> str:
    """Get the Liquidsoap Harbor URL from settings or use the default."""
    settings = get_settings()
    return settings.liquidsoap_harbor_url or LIQUIDSOAP_HARBOR_URL


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
        return {"status": "error", "message": "Cannot connect to Liquidsoap"}
    except httpx.HTTPStatusError as exc:
        logger.error(
            "liquidsoap_http_error",
            harbor_url=harbor_url,
            status_code=exc.response.status_code,
        )
        return {"status": "error", "message": f"Liquidsoap returned {exc.response.status_code}"}
    except httpx.HTTPError:
        logger.exception("liquidsoap_push_error", harbor_url=harbor_url)
        return {"status": "error", "message": "Failed to push track to Liquidsoap"}
