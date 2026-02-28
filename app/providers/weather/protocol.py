"""Weather provider protocol and result model."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class WeatherResult(BaseModel):
    """Structured weather data returned by any WeatherAdapter."""

    location: str = Field(..., description="Resolved city/area name")
    country: str = Field(..., description="Country name")
    temp_c: str = Field(..., description="Temperature in Celsius")
    description: str = Field(..., description="Weather description (e.g., 'Clear')")
    humidity: str = Field(..., description="Humidity percentage")
    wind_kmh: str = Field(..., description="Wind speed in km/h")


@runtime_checkable
class WeatherAdapter(Protocol):
    """Protocol for weather data providers (wttr.in, OpenWeatherMap, etc.)."""

    async def get_current(self, location: str) -> WeatherResult: ...
