"""Image generation provider protocol."""

from typing import Any, Protocol


class ImageGenerationProvider(Protocol):
    """Interface for image generation providers (Leonardo, etc.)."""

    async def generate_avatar(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
        generation_params: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate an avatar and return the image URL (polling-based)."""
        ...
