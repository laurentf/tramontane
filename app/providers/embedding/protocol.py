"""Protocol for embedding generation adapters."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingAdapter(Protocol):
    """Protocol for embedding generation adapters.

    Uses structural subtyping — no inheritance required.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        ...

    @property
    def dimensions(self) -> int:
        """Embedding vector dimensions."""
        ...
