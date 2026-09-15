import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status
from app.schemas.agent_schema import RunCreateRequest, RunCreateResponse, ThreadCreateRequest, ThreadCreateResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from app.models.base import User, utc_now
from app.rbac.dependencies import get_current_user
from app.lock.redis_lock import RedisDistributedLock
from app.redis.redis_client import get_redis
from redis.asyncio import Redis
from app.models.agent import Thread, Run, ThreadStatus, RunStatus, Message, MessageRole, MessageStatus
from sqlmodel import select
from app.crud.thread_crud import thread_crud
from app.crud.run_crud import run_crud
from app.crud.message_crud import message_crud
from app.tasks.agent_tasks import execute_agent_run
from app.schemas.agent_schema import ResumeRequest, ResumeResponse
from app.crud.interrupt_crud import interrupt_crud
from app.models.agent import InterruptStatus
from app.db.session import AsyncSessionLocal
import json
from fastapi import Request
from fastapi.responses import StreamingResponse
from collections.abc import AsyncGenerator




router = APIRouter()


@router.post(
    "/thread",
    response_model=ThreadCreateResponse
)
async def create_thread(
        req: ThreadCreateRequest,
        db: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    # 要为当前用户创建新Thread
    new_thread = Thread(
        user_id=current_user.id,
        title=req.title,
        status=ThreadStatus.ACTIVE.value
    )
    db.add(new_thread)
    await db.commit()
    await db.refresh(new_thread)
    return new_thread







def _build_run_response(run: Run) -> RunCreateResponse:
    return RunCreateResponse(
        thread_id=run.thread_id,
        run_id=run.id,
        status=run.status,
        stream_url=(
            f"/api/v1/agent/threads/{run.thread_id}/runs/{run.id}/stream"
        )
    )

# 每次请求实际上都是进行一次Agent Run
@router.post(
    "/threads/{thread_id}/run",
    response_model=RunCreateResponse
)
async def create_chat_run(
        thread_id: uuid.UUID,
        req: RunCreateRequest,
        db: AsyncSession = Depends(get_session),
        redis: Redis = Depends(get_redis),
        current_user: User = Depends(get_current_user)
):
    # 1 进行鉴权
    # 鉴权放在分布式锁前面是因为分布式锁锁的是thread_id
    # 防止别的用户抢占属于当前用户的thread的锁
    existing_thread = await thread_crud.get_thread_by_id(db, thread_id)
    if existing_thread is None or existing_thread.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread不存在"
        )
    # 2获取 Thread 级分布式锁
    # 锁的粒度选择是Thread
    # 若选择 run， 则粒度太细， 无法阻止同一个 Thread 两个 Run 并发
    # 若选择 user, 则粒度太粗， 导致同一用户无法在两个或多个Thread中一起跑
    lock = RedisDistributedLock(
        redis,
        key=f"lock:thread:{thread_id}",
        ttl=30
    )
    # 两个几乎同时的并发请求过来枪锁，它们可能是同一请求，带有同一幂等键，也可能不同
    acquired = await lock.acquire()
    # 没有抢到锁的一方
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="当前会话正在处理其它请求，请稍后重试"
        )
    try:
        # 抢到锁的一方，先进行权限校验
        # 首先是Thread级别的校验
        existing_thread = await thread_crud.get_thread_by_id(db, thread_id)
        # 之前通过鉴权的时候还存在，但极小概率现在又被删除了
        if existing_thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread不存在"
            )
        # 当前Thread的状态，如果是活跃状态，则通过，反之如果是归档、删除状态，则报错
        if existing_thread.status != ThreadStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Thread 当前不可执行"
            )
        # Thread校验完毕后，开始对run进行校验
        # 首先是check then act 校验，这层校验无法兜底
        existing_run = await run_crud.get_run_by_user_idempotency_key(
            db,
            current_user.id,
            req.idempotency_key
        )
        # 当前已经有run存在了，说明已经有相同请求创建了run（因为幂等键相同）
        if existing_run is not None:
            # 这个run属于当前用户，并且和当前请求是统一幂等键
            # 但还有变数，这个run的thread_id相同和不同
            # 不同的情况说明当前用户的相同请求也发给了另一个会话窗口
            # 客户端误用 key：同一 key 指到了不同 Thread。
            # 必须明确拒绝，否则会把 A thread 的 run 返回给 B thread。
            if existing_run.thread_id != thread_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="当前请求已被其它会话Thread使用，请为新的请求生成新的幂等键"
                )
            # 运行到这里，说明当前已经有相同请求在该thread创建了run
            # 那么可以直接返回结果
            return _build_run_response(existing_run)
        # 运行到这里，说明当前幂等键对应的run还不存在
        # 我们的目的创建run
        # 但是在创建run之前，还得保证当前thread没有其它幂等键对应的活跃的run
        active_run = await run_crud.get_active_run_by_thread_id(db, thread_id)
        # 当前thread已经有正在运行的run了
        if active_run is not None:
            # 这个活跃的run可能是同一幂等键请求创建的，也可能是不同幂等键请求创建的
            # 需要进行区分
            if active_run.idempotency_key == req.idempotency_key:
                return _build_run_response(active_run)
            # 不是同一幂等键，那么就是同一用户的不同请求了
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "THREAD_HAS_ACTIVE_RUN",
                    "message": "当前 Thread 已存在正在执行的 Run",
                    "run_id": str(active_run.id),
                    "run_status": active_run.status,
                },
            )
        # 运行到这里，说明当前thread还不存在正在运行的run
        # 可以进行创建
        # 但是众所周知，以上操作都是check then act操作，并不靠谱
        # 因此还需要数据库进行兜底
        run_dict = {
            "thread_id": thread_id,
            "user_id": current_user.id,
            "idempotency_key": req.idempotency_key,
            "scope": req.scope,
            "scope_id": req.scope_id,
            "status": RunStatus.QUEUED.value,
            "trigger_type": "user_prompt"
        }
        new_run = await run_crud.create_run(db, run_dict)
        message_dict = {
            "thread_id":thread_id,
            "run_id": new_run.id,
            "role": MessageRole.USER.value,
            "content": req.prompt,
            "status": MessageStatus.SUCCESS.value
        }
        new_message = await message_crud.create_message(db, message_dict)
        existing_thread.updated_at = utc_now()
        try:
            await db.commit()
        except Exception as e:
            # rollback 必须立刻执行，否则 session 不可用。
            await db.rollback()

            # ---------- (A) 同 key 并发 → 幂等返回 ----------
            existing_run = await run_crud.get_run_by_user_idempotency_key(
                db,
                current_user.id,
                req.idempotency_key
            )
            if existing_run is not None:
                if existing_run.thread_id != thread_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "IDEMPOTENCY_KEY_MISMATCH",
                            "message": "idempotency_key 已属于其他 Thread",
                        },
                    )
                return _build_run_response(existing_run)

            # ---------- (B) 同 Thread 已有活跃 Run ----------
            active_run = await run_crud.get_active_run_by_thread_id(db, thread_id)
            if active_run is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "THREAD_HAS_ACTIVE_RUN",
                        "message": "当前 Thread 已存在正在执行的 Run",
                        "run_id": str(active_run.id),
                        "run_status": active_run.status,
                    },
                )

            # ---------- (C) 其他 IntegrityError ----------
            # 例如外键失败、NOT NULL、CHECK、未来新增的唯一索引。
            # 这不是业务冲突，不能吞成 409，必须向上抛让监控报警。
            raise
            # --------------------------------------------------------
            # 3.6 TaskIQ 入队
            # --------------------------------------------------------
            #
            # 到这里 Run 已落库为 queued。
            # 如果入队失败，不能删除 Run（它已是业务事实），
            # 而应把它标记为 failed，让用户看到错误。
            #
            # ⚠️ 遗留风险：
            #   客户端在收到 503 后用同一个 idempotency_key 重试时，
            #   会命中幂等分支，拿到这个 failed 的 Run。
            #   建议客户端在 503 时换新 key 重试，
            #   或改用 Outbox 模式异步投递（见文末说明）。
            #
        try:
            task = await execute_agent_run.kiq(
                run_id=str(new_run.id),
                thread_id=str(thread_id),
                resume=False,
                resolution=None,
            )

            # new_run.task_id = task.task_id
            # await db.commit()

        except Exception as exc:

            # 用一个新的短事务标记失败，避免污染已 commit 的状态。
            new_run.status = RunStatus.FAILED.value
            new_run.error_code = "TASK_ENQUEUE_FAILED"
            new_run.error_message = str(exc)
            new_run.finished_at = utc_now()
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "TASK_ENQUEUE_FAILED",
                    "message": "Agent 任务提交失败，请稍后重试",
                },
            )
        return _build_run_response(new_run)

    finally:
        # 不管是执行异常还是代码正常执行，锁都要正常释放
        await lock.release()


# 任务恢复，返回值应该是什么？
# 要有 thread_id，run_id, status
@router.post(
    "/threads/{thread_id}/runs/{run_id}/resume",
    response_model=ResumeResponse
)
async def resume_run(
        thread_id: uuid.UUID,
        run_id: uuid.UUID,
        req: ResumeRequest,
        redis: Redis = Depends(get_redis),
        current_user: User = Depends(get_current_user)
):
    # 先进行权限鉴定
    # Thread是否属于当前用户，是否是活跃状态
    async with AsyncSessionLocal() as db:
        thread = await thread_crud.get_thread_by_id(db, thread_id)
        # 递进关系
        # 首先thread存在
        if thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread 不存在",
            )
        # 其次thread属于当前用户
        if thread.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权操作此资源",
            )
        # 最后thread得是活跃的
        if thread.status != ThreadStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Thread 当前处于非活跃状态",
            )

    # 会话级分布式锁挡住第一波
    lock = RedisDistributedLock(
        redis,
        key=f"lock:thread:{thread_id}",
        ttl=30
    )
    acquired = await lock.acquire()
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前会话正在执行别的操作"
        )
    # 运行到这里说明请到了分布式锁，有了执行权，但还是需要数据库来兜底
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                run = await run_crud.get_run_by_id(db, run_id)
                if run is None or run.thread_id != thread_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Run不存在"
                    )
                if run.status != RunStatus.REQUIRES_ACTION.value:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"当前Run状态为{run.status}, 不可执行resume操作"
                    )
                # CAS原子更新
                result = await run_crud.update_run_status(
                    db,
                    run_id,
                    src_status=RunStatus.REQUIRES_ACTION.value,
                    dest_status=RunStatus.QUEUED.value
                )
                if result.rowcount == 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Run 状态已被并发修改",
                    )
                # cas更新成功，抢到执行权
                # 进行下一步操作，修改Interrupt的状态
                # 先获取Interrupt
                interrupt = await interrupt_crud.get_pending_interrupt(
                    db,
                    thread_id,
                    run_id
                )
                if not interrupt:
                    # 本来是要回滚的，现在是在事务中，不需要回滚了
                    # 这里进行rollback是因为前面已经有了状态更新操作，出错之前必须回滚
                    # await db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="未找到挂起状态的中断操作（可能已被处理）",
                    )
                interrupt.status = InterruptStatus.RESOLVED.value
                interrupt.resolution = req.resolution
                interrupt.resolved_by = current_user.id
                interrupt.resolved_at = utc_now()
        # 启用事务后，没必要显式提交和rollback
        # try:
        #     await db.commit()
        # except Exception as e:
        #     await db.rollback()
        #     raise HTTPException(
        #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #         detail="任务状态更新出现异常",
        #     )

        # 后续该用outbox模式进行任务投递
        # 这样一来不仅通过数据库使得任务投递具有一致性
        # 且业务代码还会变得更加简单
        try:
            await execute_agent_run.kiq(
                run_id=str(run_id),
                thread_id=str(thread_id),
                resume=True,
                resolution=req.resolution,
            )
            # commit不能放到队列下面，否则会出现队列中任务已经在运行，而路由函数却没修改的异常情况
            # await db.commit()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="恢复任务提交失败",
            )
        await redis.xadd(
            f"agent:stream:{run_id}",
            {
                "event": "human_action",
                "data": json.dumps(
                    {
                        "interrupt_id": str(interrupt.id),
                        "resolution": req.resolution
                    },
                    ensure_ascii=False
                )
            },
        )
        return ResumeResponse(
            thread_id=thread_id,
            run_id=run_id,
            status=RunStatus.QUEUED.value,
        )

    finally:
        await lock.release()


TERMINAL_STATUSES = {
            RunStatus.COMPLETED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELED.value,
        }

@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def stream_run(
    thread_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """
        该路由函数用来转发 Redis Stream 中存储的数据给前端
        Redis Stream Key:
            agent:stream:{run_id}
        客户端通过
        Last-Event-ID
        实现断线重联
    """
    # 1、首先还是要进行鉴权，防止用户越过权限监听其它人的消息
    async with AsyncSessionLocal() as db:
        thread = await thread_crud.get_thread_by_id(
            db,
            thread_id
        )
        if thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread不存在"
            )
        if thread.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该Thread"
            )
        if thread.status != ThreadStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Thread处于非活跃状态"
            )
        run = await run_crud.get_run_by_id(
            db,
            run_id
        )
        if run is None or run.status in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前Agent Run已经终止"
            )
    # 2 权限鉴定结束，开始接收消息，主要通过Redis Stream
    async def event_generator() -> AsyncGenerator[str, None]:
        redis_stream_key = f"agent:stream:{run_id}"
        last_event_id = request.headers.get("Last-Event-ID", "0-0")
        # 开始进入循环，异步阻塞读取Redis Stream
        while True:
            if await request.is_disconnected():
                return
            result = await redis.xread(
                {
                    redis_stream_key: last_event_id
                },
                # 单次读取Redis Stream中对应key中消息的最大长度
                count=50,
                # 超过15秒还没有新的数据，result就返回空列表
                block=15000
            )
            # 读取到了数据，需要读取数据并yield转发给前端
            if result:
                """
                    [
                        [
                            # 第一层元素[0]：Stream 的 Key
                            "agent:stream:e2a1b5c0-6391-4c12-9c22-921a92e1b101",
                            
                            # 第一层元素[1]：该 Stream 接收到的消息条目列表 (entries)
                            [
                                # 消息 1：(event_id, fields 字典)
                                (
                                    "1715001234567-0",
                                    {
                                        "type": "message",
                                        "data": "{\"content\": \"正在为您检索相关信息...\"}"
                                    }
                                ),
                                # 消息 2：(event_id, fields 字典)
                                (
                                    "1715001235100-0",
                                    {
                                        "type": "completed",
                                        "data": "{}"
                                    }
                                )
                            ]
                        ]
                    ]
                """
                # result是一个三层嵌套结构
                # 最外层长度取决于传入key中有新数据的key的长度
                # 有新数据的key都分别由有自己的中间层列表
                # 中间层列表长度恒为2，第一个元素是key，第二个元素是数据数组
                # 数据数组也就是最内层数据，保存的是真正的数据
                # 每个数据元素都是元组，(event_id, fields 字典)
                # 根据数据结构来读取数据
                for data in result:
                    stream_key = data[0]
                    entries = data[1]
                    # 每个数据都有event_id，Redis Stream 自动生成
                    for entry in entries:
                        event_id = entry[0]
                        fields = entry[1]
                        last_event_id = event_id
                        # event_type一定有
                        event_type = fields.get("event", "message")
                        # data不一定有
                        raw_data = fields.get("data", "{}")

                        """
                           SSE协议
                           data 必传（核心）
                           event:（可选）
                           id:（可选）
                           retry:（可选）
                           : comment（可选）
                           \n\n作为结尾表示当前数据块传输结束
                        """
                        yield (
                            f"id: {event_id}\n"
                            f"event: {event_type}\n"
                            f"data: {raw_data}\n\n"
                        )
                        # 判断是否有终止event
                        if event_type in TERMINAL_STATUSES:
                            return
                        # 进入审批阶段
                        if event_type == RunStatus.REQUIRES_ACTION.value:
                            async with AsyncSessionLocal() as db:
                                current_run = await run_crud.get_run_by_id(db, run_id)
                                if current_run is None:
                                    return
                                if current_run.status in TERMINAL_STATUSES:
                                    return
                                if current_run.status != RunStatus.REQUIRES_ACTION.value:
                                    continue

            # 超过15秒还没有读取到新数据，需要查询一下当前Run的状态，看下是不是已经结束了
            else:
                async with AsyncSessionLocal() as db:
                    current_run = await run_crud.get_run_by_id(db, run_id)
                    # 防御性编程
                    if current_run is None:
                        return
                    if current_run.status in TERMINAL_STATUSES:
                        return
                yield ": heartbeat\n\n"
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
