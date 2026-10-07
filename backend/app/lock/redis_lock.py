from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from redis.asyncio import Redis


logger = logging.getLogger(__name__)


# ==========================================================
# Lua：续期
#
# 只有当前持锁者的 token 与 Redis 中 token 一致时，
# 才允许续期。
# ==========================================================

LUA_RENEW = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""


# ==========================================================
# Lua：释放
#
# 防止：
#
# A 的锁过期
# ↓
# B 获取新锁
# ↓
# A 执行 release
# ↓
# 错误地把 B 的锁删除
#
# Token 校验可以避免这个问题。
# ==========================================================

LUA_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class LockAcquisitionError(Exception):
    """无法获取分布式锁。"""

    pass


class RedisDistributedLock:
    """
    Redis 分布式锁。

    特点：

    1. SET NX EX 原子抢锁
    2. UUID token 标识锁持有者
    3. watchdog 自动续期
    4. Lua 校验 token 后续期
    5. Lua 校验 token 后释放
    """

    def __init__(
        self,
        redis: Redis,
        key: str,
        ttl: int = 30,
    ):
        self.redis = redis
        self.key = key
        self.ttl = ttl

        # 当前锁实例唯一 token
        self.token = str(uuid.uuid4())

        self._watchdog_task: Optional[asyncio.Task] = None

    async def acquire(self) -> bool:
        """
        尝试获取锁。

        成功：
            启动 watchdog。

        失败：
            返回 False。
        """

        ok = await self.redis.set(
            self.key,
            self.token,
            nx=True,
            ex=self.ttl,
        )

        if ok:
            self._start_watchdog()
            return True

        return False

    def _start_watchdog(self) -> None:
        """
        启动后台续期任务。

        默认每 ttl / 3 续期一次。
        """

        async def _renew_loop() -> None:
            interval = max(
                self.ttl / 3,
                1.0,
            )

            consecutive_failures = 0
            max_retries = 3

            while True:
                try:
                    await asyncio.sleep(interval)

                    renewed = await self.redis.eval(
                        LUA_RENEW,
                        1,
                        self.key,
                        self.token,
                        self.ttl,
                    )

                    if not renewed:
                        logger.warning(
                            "分布式锁续期失败，"
                            "锁已释放或已被其他持有者覆盖: key=%s",
                            self.key,
                        )
                        break

                    consecutive_failures = 0

                except asyncio.CancelledError:
                    break

                except Exception as exc:
                    consecutive_failures += 1

                    logger.warning(
                        "分布式锁 watchdog 网络异常 "
                        "(%d/%d): key=%s, err=%s",
                        consecutive_failures,
                        max_retries,
                        self.key,
                        exc,
                    )

                    if consecutive_failures >= max_retries:
                        logger.error(
                            "watchdog 重试超限，"
                            "自动退出: key=%s",
                            self.key,
                        )
                        break

                    await asyncio.sleep(0.5)

        self._watchdog_task = asyncio.create_task(
            _renew_loop()
        )

    async def release(self) -> None:
        """
        释放锁。

        先停止 watchdog，
        再通过 Lua 校验 token 后删除。
        """

        if (
            self._watchdog_task
            and not self._watchdog_task.done()
        ):
            self._watchdog_task.cancel()

            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass

        try:
            await self.redis.eval(
                LUA_RELEASE,
                1,
                self.key,
                self.token,
            )

        except Exception as exc:
            logger.error(
                "释放分布式锁异常: key=%s, err=%s",
                self.key,
                exc,
            )

    async def __aenter__(self) -> RedisDistributedLock:
        acquired = await self.acquire()

        if not acquired:
            raise LockAcquisitionError(
                f"无法获取分布式锁: {self.key}"
            )

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:
        await self.release()