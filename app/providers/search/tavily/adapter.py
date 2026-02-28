"""Tavily web search adapter."""

import logging

from tavily import AsyncTavilyClient
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.providers.ai_exceptions import AIProviderError
from app.providers.search.protocol import SearchResult

logger = logging.getLogger(__name__)

_RETRYABLE = (TimeoutError, ConnectionError, OSError)


class TavilySearchAdapter:
    """Tavily web search adapter implementing the SearchAdapter protocol."""

    def __init__(
        self,
        api_key: str,
        search_depth: str = "basic",
        max_results: int = 5,
    ) -> None:
        self._client = AsyncTavilyClient(api_key=api_key)
        self._search_depth = search_depth
        self._max_results = max_results
        logger.info(
            "Initialized TavilySearchAdapter with depth=%s, max_results=%s",
            search_depth,
            max_results,
        )

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchResult]:
        try:
            response = await self._client.search(
                query=query,
                search_depth=self._search_depth,
                max_results=max_results,
            )

            results: list[SearchResult] = []
            for item in response.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        score=item.get("score"),
                    )
                )

            logger.debug("Tavily search returned %s results for: %s", len(results), query)
            return results

        except _RETRYABLE:
            raise
        except Exception as e:
            logger.error("Tavily search error: %s", e)
            raise AIProviderError(provider="tavily", message=str(e)) from e
