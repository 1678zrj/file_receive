from redis.asyncio import Redis
from redis.exceptions import LockError

class DistributedLockTimeoutError(Exception):
    """获取分布式锁超时异常"""
    pass


class AsyncDistributedLock:
    def __init__(
            self,
            redis: Redis,
            key: str,
            timeout: float = 10.0,
            blocking_timeout: float = 5.0,
    ):
        self.redis = redis
        self.key = key
        self.timeout = timeout
        self.blocking_timeout = blocking_timeout
        self._lock = self.redis.lock(
            name=self.key,
            timeout=self.timeout,
            blocking_timeout=self.blocking_timeout
        )

    async def __aenter__(self):

        pass