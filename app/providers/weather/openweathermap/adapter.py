"""OpenWeatherMap weather adapter."""

import logging

import httpx

from app.providers.ai_exceptions import AIProviderError
from app.providers.weather.protocol import WeatherResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


class OpenWeatherMapAdapter:
    """Weather adapter using OpenWeatherMap API (free tier: 1000 calls/day)."""

    def __init__(self, api_key: str | None = None) -> None:
        if not api_key:
            msg = "OPENWEATHER_API_KEY required for OpenWeatherMap provider"
            raise ValueError(msg)
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "tramontane/1.0"},
        )

    async def get_current(self, location: str) -> WeatherResult:
        try:
            resp = await self._client.get(
                _BASE_URL,
                params={
                    "q": location,
                    "appid": self._api_key,
                    "units": "metric",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            return WeatherResult(
                location=data["name"],
                country=data["sys"]["country"],
                temp_c=str(round(data["main"]["temp"])),
                description=data["weather"][0]["description"].capitalize(),
                humidity=str(data["main"]["humidity"]),
                wind_kmh=str(round(data["wind"]["speed"] * 3.6)),
            )
        except (httpx.HTTPStatusError, KeyError, IndexError) as e:
            logger.exception("OpenWeatherMap error for %s", location)
            raise AIProviderError(provider="openweathermap", message=str(e)) from e
        except httpx.HTTPError as e:
            logger.exception("OpenWeatherMap connection error for %s", location)
            raise AIProviderError(provider="openweathermap", message=str(e)) from e
