"""Leonardo AI adapter for avatar image generation."""

from __future__ import annotations

import asyncio

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"
PHOENIX_MODEL_ID = "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"

# Placeholder avatar URL returned when no API key is configured (dev mode).
_PLACEHOLDER_AVATAR = (
    "https://placehold.co/512x512/1a1a2e/00d4ff?text=Avatar&font=press-start-2p"
)


class LeonardoAdapter:
    """Image generation adapter backed by the Leonardo AI REST API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
            "accept": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def generate_avatar(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        model_id: str | None = None,
        preset_style: str | None = None,
        alchemy: bool | None = None,
        guidance_scale: float | None = None,
    ) -> str:
        """Submit an avatar generation request.

        Returns the generation ID for polling, or a placeholder URL
        if the API key is not configured.
        """
        if not self.is_configured:
            logger.warning("leonardo_not_configured", action="generate_avatar")
            return _PLACEHOLDER_AVATAR

        body: dict = {
            "prompt": prompt,
            "modelId": model_id or PHOENIX_MODEL_ID,
            "width": width,
            "height": height,
            "num_images": 1,
        }
        if preset_style is not None:
            body["presetStyle"] = preset_style
        if alchemy is not None:
            body["alchemy"] = alchemy
        if guidance_scale is not None:
            body["guidance_scale"] = guidance_scale

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{BASE_URL}/generations",
                    headers=self._headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

            # Defensive parsing: primary key path, then fallback
            generation_id: str | None = None
            if "sdGenerationJob" in data:
                generation_id = data["sdGenerationJob"].get("generationId")
            if not generation_id and "generationJob" in data:
                generation_id = data["generationJob"].get("generationId")

            if not generation_id:
                logger.error("leonardo_missing_generation_id", response=data)
                raise ValueError("Leonardo API did not return a generation ID")

            logger.info("leonardo_generation_submitted", generation_id=generation_id)
            return generation_id

        except httpx.HTTPError as exc:
            logger.error("leonardo_http_error", error=str(exc))
            raise

    async def poll_generation(
        self,
        generation_id: str,
        *,
        max_polls: int = 30,
        interval: float = 2.0,
    ) -> str | None:
        """Poll for generation completion and return the image URL.

        Returns the first generated image URL on success, or None on
        failure/timeout.
        """
        logger.info("leonardo_polling_start", generation_id=generation_id, max_polls=max_polls)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                for attempt in range(max_polls):
                    resp = await client.get(
                        f"{BASE_URL}/generations/{generation_id}",
                        headers=self._headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    gen_data = data.get("generations_by_pk", {})
                    status = gen_data.get("status")

                    if status == "COMPLETE":
                        images = gen_data.get("generated_images", [])
                        if images:
                            url = images[0].get("url")
                            logger.info("leonardo_generation_complete", url=url)
                            return url
                        logger.warning("leonardo_complete_no_images", generation_id=generation_id)
                        return None

                    if status == "FAILED":
                        logger.warning("leonardo_generation_failed", generation_id=generation_id)
                        return None

                    logger.debug(
                        "leonardo_poll_pending",
                        generation_id=generation_id,
                        attempt=attempt + 1,
                        status=status,
                    )
                    await asyncio.sleep(interval)

        except httpx.HTTPError as exc:
            logger.error("leonardo_poll_http_error", error=str(exc))
            return None

        logger.warning("leonardo_poll_timeout", generation_id=generation_id)
        return None
