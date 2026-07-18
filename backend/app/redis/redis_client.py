from redis.asyncio import Redis
from app.core.config import settings


class RedisManager:
    _client: Redis | None = None

    @classmethod
    async def init(cls):
        """初始化连接池"""
        if not cls._client:
            cls._client = Redis.from_url(
                url=settings.redis_url,
                max_connections=settings.redis_max_connections,
                socket_keepalive=settings.redis_socket_keepalive,
                decode_responses=True,
                encoding="utf-8"
            )
        await cls._client.ping()
        print("Redis连接成功")

    @classmethod
    def get_client(cls) -> Redis:
        if cls._client is None:
            raise RuntimeError("Redis未初始化，请先调用init()")
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.aclose()
            cls._client = None

# 加上async，Depend依赖函数可以直接在异步主线程执行，
# 否则会放到线程池里加大开销，增加无意义的线程调用开销
async def get_redis() -> Redis:
    return RedisManager.get_client()

