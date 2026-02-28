"""Provider registry for dynamic adapter instantiation.

Maps provider names (from config) to adapter classes.
Allows switching providers via environment variables.
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
        registry = ProviderRegistry[SomeAdapter]("SomeType")
        registry.register("name", SomeAdapterImpl)
        adapter = registry.create("name", api_key=...)
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
# Global registries — register adapters here as you add providers
# =============================================================================
# Example:
#   from app.providers.llm.protocol import LLMAdapter
#   from app.providers.llm.mistral import MistralLLMAdapter
#   llm_registry: ProviderRegistry[LLMAdapter] = ProviderRegistry("LLM")
#   llm_registry.register("mistral", MistralLLMAdapter)
