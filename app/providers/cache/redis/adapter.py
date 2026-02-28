"""Redis cache adapter implementation using async redis."""

import logging

import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisCacheAdapter:
    """Async Redis implementation of CacheProvider."""

    def __init__(self, redis_url: str) -> None:
        self._client = aioredis.from_url(redis_url)

    async def get(self, key: str) -> str | None:
        try:
            value = await self._client.get(key)
            return value.decode("utf-8") if value else None
        except RedisError as e:
            logger.warning("Redis get failed for key %s: %s", key, e)
            return None

    async def set(self, key: str, value: str, ttl: int) -> bool:
        try:
            await self._client.setex(key, ttl, value)
            return True
        except RedisError as e:
            logger.warning("Redis set failed for key %s: %s", key, e)
            return False

    async def set_if_absent(self, key: str, value: str, ttl: int) -> bool:
        try:
            return bool(await self._client.set(key, value, ex=ttl, nx=True))
        except RedisError as e:
            logger.warning("Redis setnx failed for key %s: %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        try:
            await self._client.delete(key)
            return True
        except RedisError as e:
            logger.warning("Redis delete failed for key %s: %s", key, e)
            return False
