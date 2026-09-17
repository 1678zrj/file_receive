# from taskiq_redis import ListQueueBroker
# from taskiq import TaskiqEvents, TaskiqState
# from app.core.config import settings
# from app.redis.redis_client import RedisManager
# from app.core.rag_deps import rag_container
#
#
# broker = ListQueueBroker(
#     settings.redis_url,
#     socket_timeout=None,        # 关键：BRPOP 无限期阻塞，读超时必须为 None
#     socket_connect_timeout=5.0, # 只限制建连，不影响读
# )
#
#
# @broker.on_event(TaskiqEvents.WORKER_STARTUP)
# async def _worker_startup(state: TaskiqState):
#     await RedisManager.init()
#     await rag_container.startup()
#     print("TaskIQ worker started, redis ready")
#
#
# @broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
# async def _worker_shutdown(state: TaskiqState):
#     await rag_container.shutdown()
#     await RedisManager.close()
#     print("TaskIQ worker stopped")
#
#
# async def startup_broker() -> None:
#     if not broker.is_worker_process:
#         await broker.startup()
#
#
# async def shutdown_broker() -> None:
#     if not broker.is_worker_process:
#         await broker.shutdown()
from taskiq import TaskiqEvents, TaskiqState
from taskiq_redis import ListQueueBroker

from app.core.config import settings
from app.core.rag_deps import rag_container
from app.redis.redis_client import RedisManager


"""
    定义两个broker是为了做到资源隔离，
    比如merge_broker只需要Redis客户端
    而agent_broker还需要rag_container
    实际上真正做到两个worker的隔离靠的是指定queue_name
    不指定queue_name就默认到同一个消息队列中，队列名默认是taskiq
    这就会导致merge_worker和agent_worker
    从同一个消息队列中抢不属于它们的任务
"""
# 1. 专门处理文件合并的 Broker
merge_broker = ListQueueBroker(
    settings.redis_url,
    queue_name="merge_queue",
    socket_timeout=None,
    socket_connect_timeout=5.0,
)

# 2. 专门处理 Agent 的 Broker
agent_broker = ListQueueBroker(
    settings.redis_url,
    queue_name="agent_queue",
    socket_timeout=None,
    socket_connect_timeout=5.0,
)


# ---------- merge_broker Worker 事件 (不需要加载沉重的 RAG/Milvus) ----------
@merge_broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _merge_worker_startup(state: TaskiqState):
    await RedisManager.init()
    # await rag_container.startup()
    print("Merge worker started, redis ready")


@merge_broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _merge_worker_shutdown(state: TaskiqState):
    await RedisManager.close()
    print("Merge worker stopped")


# ---------- agent_broker Worker 事件 (需要 Redis + RAG/Milvus) ----------
@agent_broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _agent_worker_startup(state: TaskiqState):
    await RedisManager.init()
    await rag_container.startup()
    print("Agent worker started, rag ready")


@agent_broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _agent_worker_shutdown(state: TaskiqState):
    await rag_container.shutdown()
    await RedisManager.close()
    print("Agent worker stopped")


# ---------- 供 FastAPI 主进程调用的统一管理函数 ----------
async def startup_brokers() -> None:
    """FastAPI 启动时，初始化生产者客户端"""
    if not merge_broker.is_worker_process:
        await merge_broker.startup()
    if not agent_broker.is_worker_process:
        await agent_broker.startup()


async def shutdown_brokers() -> None:
    """FastAPI 退出时，释放连接"""
    if not merge_broker.is_worker_process:
        await merge_broker.shutdown()
    if not agent_broker.is_worker_process:
        await agent_broker.shutdown()