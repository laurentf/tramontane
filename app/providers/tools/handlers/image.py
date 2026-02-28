"""Image generation tool handler (polling-based).

Wraps any ImageGenerationProvider (Leonardo, etc.) and exposes it as a tool.
Uses polling for completion (tramontane uses synchronous avatar generation).
"""

import logging
from typing import Any

from app.providers.image.leonardo.adapter import LeonardoAdapter
from app.providers.tools.protocol import ToolContext, ToolResponse, ToolSchema

logger = logging.getLogger(__name__)


class ImageToolHandler:
    """Tool handler for image generation via polling."""

    DEFAULT_DESCRIPTION = (
        "Generate an image from a text description. Use when the user "
        "explicitly asks for an image, artwork, picture, or visual content."
    )

    def __init__(
        self,
        adapter: LeonardoAdapter,
        *,
        description: str | None = None,
        default_width: int = 512,
        default_height: int = 512,
    ) -> None:
        self._adapter = adapter
        self._description = description or self.DEFAULT_DESCRIPTION
        self._default_width = default_width
        self._default_height = default_height

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="generate_image",
            description=self._description,
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "Detailed description of the image to generate. "
                            "Be specific about style, composition, colors, and mood."
                        ),
                    },
                },
                "required": ["prompt"],
            },
        )

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResponse:
        prompt = arguments.get("prompt", "")
        if not prompt:
            return ToolResponse(success=False, result="No image prompt provided")

        logger.info("Image generation request: %s", prompt[:100])

        try:
            generation_id = await self._adapter.generate_avatar(
                prompt=prompt,
                width=self._default_width,
                height=self._default_height,
            )

            if not generation_id:
                return ToolResponse(
                    success=False,
                    result="Image generation failed to start",
                    metadata={"prompt": prompt},
                )

            image_url = await self._adapter.poll_generation(generation_id)

            if not image_url:
                return ToolResponse(
                    success=False,
                    result="Image generation timed out",
                    metadata={"prompt": prompt, "generation_id": generation_id},
                )

            return ToolResponse(
                success=True,
                result=f"Image generated successfully: {image_url}",
                metadata={
                    "image_url": image_url,
                    "generation_id": generation_id,
                    "prompt": prompt,
                },
            )

        except Exception as e:
            logger.exception("Image generation failed: %s", prompt[:100])
            return ToolResponse(
                success=False,
                result=f"Image generation failed: {e}",
                metadata={"prompt": prompt},
            )
