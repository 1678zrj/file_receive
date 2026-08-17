from taskiq_redis import ListQueueBroker
from taskiq import TaskiqEvents, TaskiqState
from app.core.config import settings
from app.redis.redis_client import RedisManager

broker = ListQueueBroker(
    settings.redis_url,
    socket_timeout=None,        # 关键：BRPOP 无限期阻塞，读超时必须为 None
    socket_connect_timeout=5.0, # 只限制建连，不影响读
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _worker_startup(state: TaskiqState):
    await RedisManager.init()
    print("TaskIQ worker started, redis ready")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _worker_shutdown(state: TaskiqState):
    await RedisManager.close()
    print("TaskIQ worker stopped")


async def startup_broker() -> None:
    if not broker.is_worker_process:
        await broker.startup()


async def shutdown_broker() -> None:
    if not broker.is_worker_process:
        await broker.shutdown()
