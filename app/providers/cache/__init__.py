"""Cache provider protocol."""

from typing import Protocol


class CacheProvider(Protocol):
    """Interface for cache providers (Redis, Memcached, in-memory, etc.)."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl: int) -> bool: ...

    async def set_if_absent(self, key: str, value: str, ttl: int) -> bool: ...

    async def delete(self, key: str) -> bool: ...
