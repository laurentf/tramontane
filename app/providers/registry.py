"""Provider registry for dynamic adapter instantiation.

Maps provider names (from config) to adapter classes.
Allows switching providers via environment variables.

Usage:
    LLM_PROVIDER=mistral  → MistralLLMAdapter
"""

import structlog

logger = structlog.get_logger(__name__)


class ProviderNotFoundError(Exception):
    """Raised when a requested provider is not registered."""

    def __init__(self, provider_type: str, provider_name: str, available: list[str]):
        self.provider_type = provider_type
        self.provider_name = provider_name
        self.available = available
        super().__init__(
            f"Unknown {provider_type} provider: '{provider_name}'. "
            f"Available: {available}"
        )


class ProviderRegistry[T]:
    """Generic registry for provider adapters.

    Usage:
        llm_registry = ProviderRegistry[LLMAdapter]("LLM")
        llm_registry.register("mistral", MistralLLMAdapter)
        adapter = llm_registry.create("mistral", api_key=..., model=...)
    """

    def __init__(self, provider_type: str) -> None:
        self._provider_type = provider_type
        self._providers: dict[str, type[T]] = {}

    def register(self, name: str, adapter_class: type[T]) -> None:
        """Register a provider adapter class."""
        self._providers[name.lower()] = adapter_class
        logger.debug("Registered %s provider: %s", self._provider_type, name)

    def create(self, name: str, **kwargs: object) -> T:
        """Create an adapter instance for the named provider."""
        name_lower = name.lower()
        adapter_class = self._providers.get(name_lower)

        if not adapter_class:
            raise ProviderNotFoundError(
                provider_type=self._provider_type,
                provider_name=name,
                available=list(self._providers.keys()),
            )

        logger.info(
            "Creating %s adapter: %s (%s)",
            self._provider_type, name, adapter_class.__name__,
        )
        return adapter_class(**kwargs)

    def get_class(self, name: str) -> type[T] | None:
        """Get adapter class without instantiating."""
        return self._providers.get(name.lower())

    @property
    def available(self) -> list[str]:
        """List of registered provider names."""
        return list(self._providers.keys())

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._providers


# =============================================================================
# Global registries (populated at import time)
# =============================================================================

from app.providers.analyzer.mistral.adapter import MistralAnalyzerAdapter  # noqa: E402
from app.providers.analyzer.protocol import AnalyzerAdapter  # noqa: E402
from app.providers.embedding.mistral.adapter import MistralEmbeddingAdapter  # noqa: E402
from app.providers.embedding.protocol import EmbeddingAdapter  # noqa: E402
from app.providers.image import ImageGenerationProvider  # noqa: E402
from app.providers.image.leonardo.adapter import LeonardoAdapter  # noqa: E402
from app.providers.llm.mistral import MistralLLMAdapter  # noqa: E402
from app.providers.llm.protocol import LLMAdapter  # noqa: E402
from app.providers.search.protocol import SearchAdapter  # noqa: E402
from app.providers.search.tavily.adapter import TavilySearchAdapter  # noqa: E402
from app.providers.speech.stt import STTProvider  # noqa: E402
from app.providers.speech.stt.mistral.adapter import MistralSTTAdapter  # noqa: E402
from app.providers.speech.tts.elevenlabs.adapter import ElevenLabsTTSAdapter  # noqa: E402
from app.providers.weather.openweathermap.adapter import OpenWeatherMapAdapter  # noqa: E402
from app.providers.weather.protocol import WeatherAdapter  # noqa: E402

# LLM providers
llm_registry: ProviderRegistry[LLMAdapter] = ProviderRegistry("LLM")
llm_registry.register("mistral", MistralLLMAdapter)

# Embedding providers
embedding_registry: ProviderRegistry[EmbeddingAdapter] = ProviderRegistry("Embedding")
embedding_registry.register("mistral", MistralEmbeddingAdapter)

# Search providers
search_registry: ProviderRegistry[SearchAdapter] = ProviderRegistry("Search")
search_registry.register("tavily", TavilySearchAdapter)

# Image providers
image_registry: ProviderRegistry[ImageGenerationProvider] = ProviderRegistry("Image")
image_registry.register("leonardo", LeonardoAdapter)

# STT providers
stt_registry: ProviderRegistry[STTProvider] = ProviderRegistry("STT")
stt_registry.register("mistral", MistralSTTAdapter)

# TTS providers — no protocol yet, just the adapter
tts_registry: ProviderRegistry = ProviderRegistry("TTS")
tts_registry.register("elevenlabs", ElevenLabsTTSAdapter)

# Weather providers
weather_registry: ProviderRegistry[WeatherAdapter] = ProviderRegistry("Weather")
weather_registry.register("openweathermap", OpenWeatherMapAdapter)

# Analyzer providers (structured JSON analysis)
analyzer_registry: ProviderRegistry[AnalyzerAdapter] = ProviderRegistry("Analyzer")
analyzer_registry.register("mistral", MistralAnalyzerAdapter)
