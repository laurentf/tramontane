"""Weather tool handler."""

import logging
from typing import Any

from app.providers.tools.protocol import ToolContext, ToolResponse, ToolSchema
from app.providers.weather.protocol import WeatherAdapter

logger = logging.getLogger(__name__)


class WeatherToolHandler:
    """Tool handler for weather lookup capabilities."""

    DEFAULT_DESCRIPTION = (
        "Get current weather for a location. Use when the user asks about weather, "
        "temperature, or conditions in any city or place."
    )

    def __init__(
        self,
        adapter: WeatherAdapter,
        *,
        description: str | None = None,
    ) -> None:
        self._adapter = adapter
        self._description = description or self.DEFAULT_DESCRIPTION

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="weather",
            description=self._description,
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location",
                    },
                },
                "required": ["location"],
            },
        )

    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResponse:
        location = arguments.get("location", "").strip()
        if not location:
            return ToolResponse(success=False, result="No location provided.")

        logger.info("Weather lookup: %s", location)

        try:
            result = await self._adapter.get_current(location)

            return ToolResponse(
                success=True,
                result=(
                    f"{result.location}, {result.country}: "
                    f"{result.temp_c}\u00b0C, {result.description}. "
                    f"Humidity {result.humidity}%, wind {result.wind_kmh} km/h."
                ),
            )
        except Exception as e:
            logger.exception("Weather lookup failed for %s", location)
            return ToolResponse(
                success=False,
                result=f"Weather lookup failed: {e}",
            )
