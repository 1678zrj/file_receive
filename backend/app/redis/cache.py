import asyncio

from redis.asyncio import Redis
from fastapi import Depends
from app.redis.redis_client import get_redis


class CacheService:
    def __init__(
            self,
            redis: Redis
    ):
        self.redis = redis

    async def get(self, key: str):
        value = await self.redis.get(key)
        if value:
            return value
        return None

    async def set(
            self,
            key: str,
            value,
            expire: int = 300
    ):
        await self.redis.set(
            key,
            value,
            ex=expire
        )

    async def delete(self, key):
        await self.redis.delete(key)


async def get_cache_service(
        redis: Redis = Depends(get_redis)
):
    return CacheService(redis=redis)

