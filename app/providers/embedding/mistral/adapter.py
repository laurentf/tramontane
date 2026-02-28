"""Mistral AI embedding adapter."""

import logging
from typing import ClassVar

from mistralai import Mistral
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.providers.mistral_utils import RETRYABLE_ERRORS, raise_provider_error

logger = logging.getLogger(__name__)


class MistralEmbeddingAdapter:
    """Mistral AI embedding adapter.

    Implements EmbeddingAdapter protocol via structural subtyping.
    """

    _MODEL_DIMENSIONS: ClassVar[dict[str, int]] = {
        "mistral-embed": 1024,
    }

    def __init__(
        self, api_key: str, model: str = "mistral-embed", dimensions: int | None = None
    ) -> None:
        self._client = Mistral(api_key=api_key)
        self._model = model
        self._dimensions = dimensions or self._MODEL_DIMENSIONS.get(model, 1024)
        logger.info("Initialized MistralEmbeddingAdapter: %s (%dd)", model, self._dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @retry(
        retry=retry_if_exception_type(RETRYABLE_ERRORS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self._client.embeddings.create_async(
                model=self._model,
                inputs=texts,
            )

            return [item.embedding for item in response.data]

        except RETRYABLE_ERRORS:
            raise
        except Exception as e:
            raise_provider_error("embedding", e)
