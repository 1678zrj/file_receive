import asyncio
import json
import logging
import uuid

from langchain_core.tools import BaseTool
from sqlmodel import update
from app.db.worker_session import AsyncSessionWorker

from app.core.rag_deps import rag_container
from langchain_core.messages import HumanMessage, AIMessageChunk, AIMessage, ToolMessage, ToolCall
from langgraph.types import Command
from app.redis.redis_client import RedisManager
from app.models.base import utc_now
from app.core.broker import agent_broker
from typing import Any
from app.lock.redis_lock import RedisDistributedLock
from app.crud.run_crud import run_crud
from app.crud.thread_crud import thread_crud
from app.crud.message_crud import message_crud
from app.models.agent import RunStatus, Run, MessageStatus, Message, MessageRole, Interrupt, InterruptStatus
from sqlalchemy.orm.attributes import flag_modified
from redis.asyncio import Redis
from app.crud.interrupt_crud import interrupt_crud
from app.rag_agent.graph_container import graph_container

logger = logging.getLogger(__name__)

MAX_TOOL_OUTPUT_CHARS = 10_000
DB_THROTTLE_FLUSH_INTERVAL = 5
CANCEL_CHECK_INTERVAL = 10


async def publish_event(
    redis_client: Redis,
    run_id: uuid.UUID,
    event_type: str,
    data: Any = None
):
    """
        将当前事件写入Redis Stream
    """
    try:
        payload_json = json.dumps(data if data is not None else {}, ensure_ascii=False)
        await redis_client.xadd(
            f"agent:stream:{run_id}",
            # event和data统一打包，
            # 随后FastAPI路由函数取到数据后分别提取event和data
            {
                "event": event_type,
                "data": payload_json
            }
        )
    except Exception as e:
        # 降级处理：记录告警，但不中断主业务线程
        # 真正的执行结果仍会被 flush_to_db 持久化到 PostgreSQL
        logger.warning("Failed to publish event to Redis stream (run=%s, event=%s): %s", run_id, event_type, e)

class RunExecutionAccumulator:
    """
    一个Run执行期间的中间结果累计器
    """
    def __init__(
            self,
            initial_parts: list[dict[str, Any]] | None = None
    ):
        self.parts: list[dict[str, Any]] = (
            initial_parts if list(initial_parts)
            else []
        )
        self.tool_refs: dict[str, Any] = {}
        if initial_parts:
            self._restore_tool_refs_from_parts(initial_parts)

    def _restore_tool_refs_from_parts(self, parts: list[dict[str, Any]]):
        for part in parts:
            p_type = part.get("type")
            tid = part.get("tool_call_id")
            if not tid:
                continue
            if p_type == "tool_call":
                self.tool_refs[tid] = {
                    "id": tid,
                    "name": part.get("name"),
                    "args": part.get("args", {}),
                    "status": part.get("status")
                }
            elif p_type == "tool_result":
                status = part.get("status", "completed")
                content = part.get("content")
                if tid in self.tool_refs:
                    self.tool_refs[tid]["status"] = status
                    self.tool_refs[tid]["output"] = content
                else:
                    self.tool_refs[tid] = {
                    "id": tid,
                    "name": None,
                    "args": {},
                    "status": status,
                    "output": content,
                    }
    def add_thought_delta(self, delta: str):
        if not delta:
            return
        if self.parts and self.parts[-1].get("type") == "thought":
            self.parts[-1]["content"] = (
                self.parts[-1].get("content", "") + delta
            )

        else:
            self.parts.append(
                {
                    "type": "thought",
                    "content":delta
                }
            )
    def add_text_delta(self, delta: str):
        if not delta:
            return
        if self.parts and self.parts[-1].get("type") == "text":
            self.parts[-1]["content"] = (
                self.parts[-1].get("content", "") + delta
            )
        else:
            self.parts.append(
                {
                    "type": "text",
                    "content":delta
                }
            )
    def register_tool_call(self, tool_call: ToolCall) -> bool:
        tool_call_id = tool_call["id"]
        if not tool_call_id:
            return False
        if tool_call_id in self.tool_refs:
            return False
        # 一个工具调用，需要具备
        # id, args, name, status
        tool_ref = {
            "id": tool_call_id,
            "name": tool_call.get("name"),
            "args": tool_call.get("args"),
            "status": "running"
        }
        self.tool_refs[tool_call_id] = tool_ref
        # parts中涵盖了各种类型的消息，因此还需多加一个类型来标识
        self.parts.append(
            {
                "type": "tool_call",
                "tool_call_id": tool_call_id,
                "name": tool_call.get("name"),
                "args": tool_call.get("args"),
                "status": "running"
            }
        )
        return True

    def complete_tool_call(
            self,
            tool_message: ToolMessage
    ) -> tuple[bool, str]:
        tool_call_id = tool_message.tool_call_id
        # 防御性编程
        if not tool_call_id:
            return False, "completed"
        if (
            tool_call_id in self.tool_refs
            and self.tool_refs[tool_call_id].get("status") in ("completed", "failed")
        ):
            return False, self.tool_refs["status"]
        # 真正要做的
        # 注意status需要自己显式设置，在langgraph的工具调用执行节点中
        msg_status = tool_message.status
        final_status = "failed" if msg_status == "error" else "completed"
        content = tool_message.content
        content_str = (
            content[:MAX_TOOL_OUTPUT_CHARS]
            if isinstance(content, str)
            else str(content)[:MAX_TOOL_OUTPUT_CHARS]
        )
        if tool_call_id in self.tool_refs:
            self.tool_refs[tool_call_id]["status"] = final_status
            self.tool_refs[tool_call_id]["output"] = content_str
        else:
            self.tool_refs[tool_call_id] = {
                "tool_call_id": tool_call_id,
                "name": None,
                "args": {},
                "status": final_status,
                "output": content_str
            }
        for part in reversed(self.parts):
            if part.get("type") == "tool_call" and part.get("tool_call_id") == tool_call_id:
                part["status"] = final_status
                break
        self.parts.append(
            {
                "type": "tool_result",
                "tool_call_id": tool_call_id,
                "content": content_str,
                "status": final_status
            }
        )
        return True, final_status




    @property
    def content(self) -> str:
        return "".join(
            [
                part.get("content", "")
                for part in self.parts
                if part.get("type")=="text"
            ]
        )

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return list(self.tool_refs.values())

    @property
    def citations(self) -> list[dict[str, Any]]:
        """向下兼容 Message.citations 字段，若后续引入 RAG 引用可在此扩展"""
        return []

async def flush_to_db(
    run_id: uuid.UUID,
    thread_id: uuid.UUID,
    accumulator: RunExecutionAccumulator,
    status: str = MessageStatus.PENDING.value
):
    """
        将当前的消息持久化到DB
    """
    async with AsyncSessionWorker() as db:
        message = await message_crud.get_assistant_message_by_run_id(db, run_id)
        # 这是非resume的情况
        if message is None:
            message_data_dict = {
                "thread_id": thread_id,
                "run_id": run_id,
                "role": MessageRole.ASSISTANT.value,
                "content": accumulator.content,
                "parts": accumulator.parts,
                "tool_calls": accumulator.tool_calls,
                "citations": accumulator.citations,
                "status": status
            }
            message = await message_crud.create_message(
                db,
                message_data_dict
            )
        else:
            message.content = accumulator.content
            message.parts = list(accumulator.parts)
            message.tool_calls = list(accumulator.tool_calls)
            message.status = status
            # 对于可变对象，必须显示告知session进行更新
            flag_modified(message, "parts")
            flag_modified(message,"tool_calls")
            flag_modified(message, "citations")
        await db.commit()


@agent_broker.task(task_name="agent_run_task")
async def execute_agent_run(
        run_id: str,
        thread_id: str,
        resume: bool = False,
        resolution: dict[str, Any] | list[dict[str, Any]] | None = None
):
    """
        TaskIQ Agent Worker
        核心流程：
            1、 上分布式锁（带看门狗）
            2、 乐观锁兜底
            3、 获取当前状态
    """
    run_uuid = uuid.UUID(run_id)
    thread_uuid = uuid.UUID(thread_id)
    redis_client = RedisManager.get_client()

    worker_lock = RedisDistributedLock(
        redis_client,
        key=f"lock:agent:run:{run_id}",
        ttl=30
    )
    acquired = await worker_lock.acquire()
    if not acquired:
        logger.warning(
            "Run worker already exists: %s",
            run_id,
        )
        return
    stream_key = f"agent:stream:{run_id}"
    try:
        # 先检验当前的run和Thread是否匹配
        async with AsyncSessionWorker() as db:
            run = await run_crud.get_run_by_id(
                db,
                run_uuid
            )
            if run is None:
                logger.error(
                    "Run not found: %s",
                    run_id,
                )
                return
            if run.thread_id != thread_uuid:
                logger.error(
                    "Run/thread mismatch: run=%s thread=%s expected=%s",
                    run_id,
                    run.thread_id,
                    thread_id,
                )
                return
            thread = await thread_crud.get_thread_by_id(
                db,
                thread_uuid
            )
            if thread is None:
                logger.error(
                    "Thread not found: %s",
                    thread_id,
                )
                return
            # 开始 乐观锁 CAS 兜底（真正底牌）
            allowed_statuses = (
                [RunStatus.QUEUED.value]
                if resume
                else [RunStatus.QUEUED.value]
            )
            stmt = update(Run).where(
                Run.id == run_uuid,
                Run.thread_id == thread_uuid,
                Run.status.in_(allowed_statuses)
            ).values(
                status=RunStatus.IN_PROGRESS.value,
                started_at=(Run.started_at or utc_now())
            )
            result = await db.execute(stmt)
            if result.rowcount != 1:
                logger.warning(
                    "Run status transition rejected: run=%s resume=%s",
                    run_id,
                    resume,
                )
                return
            await db.commit()
            # 乐观锁更新成功
            # 可以正常执行流程了
            run_scope = run.scope
            run_scope_id = run.scope_id
            # 这里要考虑Resume 时加载已有 assistant parts
            initial_parts: list[dict[str, Any]] = []
            assistant_message = await message_crud.get_assistant_message_by_run_id(
                db,
                run_uuid
            )
            if assistant_message is not None and assistant_message.parts:
                initial_parts = list(assistant_message.parts)
        # 初始化 accumulator
        accumulator = RunExecutionAccumulator(
            initial_parts
        )
        # 如果是初次的话，可以进行消息初始化
        await flush_to_db(
            run_uuid,
            thread_uuid,
            accumulator,
            MessageStatus.PENDING.value
        )
        await publish_event(
            redis_client,
            run_uuid,
            "in_progress",
            {}
        )
        # 接下来是graph的正式运行
        # 先获取用户的输入
        if resume:
            # 如果是中断响应
            graph_input = Command(
                resume=resolution or {}
            )
        # 不是中断响应，则获取用户启动当前Run的输入
        else:
            # 查询当前run对应的用户Message
            async with AsyncSessionWorker() as db:
                user_message = await message_crud.get_user_message_by_run_id(
                    db,
                    run_uuid
                )
                if user_message is None:
                    raise RuntimeError(
                        f"User message not found for run {run_id}"
                    )
            graph_input = {"messages": [HumanMessage(content=user_message.content)]}
        config = {
            "configurable": {
                "thread_id": str(thread_uuid),
                "scope": run_scope,
                "scope_id": run_scope_id
            }
        }
        graph = graph_container.graph
        chunk_count = 0
        # 上一次数据落库时间
        last_db_flush = asyncio.get_running_loop().time()
        async for chunk in graph.astream(
            graph_input,
            config=config,
            stream_mode=["messages", "updates"],
            version="v2"
        ):
            chunk_count += 1
            """
                这里要做取消信号检测，后续补上
            """
            chunk_type = chunk.get("type")
            data = chunk.get("data")
            # 当stream_mode是messages的情况
            # 这种情况下会输出会有两种输出，一种是AIMessageChunk
            # 一种是ToolMessage，因此要做类型识别
            if chunk_type == "messages":
                message, metadata = data
                if isinstance(message, AIMessageChunk):
                    reasoning_content = message.additional_kwargs.get("reasoning_content")
                    if reasoning_content:
                        accumulator.add_thought_delta(reasoning_content)
                        await publish_event(
                            redis_client,
                            run_uuid,
                            "thought_delta",
                            {"delta": reasoning_content}
                        )
                    content = message.content
                    if content:
                        accumulator.add_text_delta(content)
                        await publish_event(
                            redis_client,
                            run_uuid,
                            "text_delta",
                            {"delta": content}
                        )
            # stream_mode=updates模式下的输出
            # 一般是每个节点更新的消息
            elif chunk_type == "updates":
                """
                    data是
                    {
                        "node_name": {
                            "messages": list[BaseMessage]   
                        }
                    }
                    格式的字典
                """
                if not isinstance(data, dict):
                    continue
                for node_name, update_data in data.items():
                    # 防御性编程
                    if isinstance(update_data, dict) and "messages" in update_data:
                        for message in update_data["messages"]:
                            # 处理函数工具调用
                            if isinstance(message, AIMessage):
                                # AIMessage的思考内容和输出内容都已被记录，这里只需要处理工具调用
                                for tool_call in message.tool_calls:
                                    is_success = accumulator.register_tool_call(tool_call)
                                    if is_success:
                                        await publish_event(
                                            redis_client,
                                            run_uuid,
                                            "tool_call",
                                            tool_call
                                        )
                            # 处理工具调用结果
                            elif isinstance(message, ToolMessage):
                                # 状态返回值有completed和failed
                                is_new, tool_status = accumulator.complete_tool_call(message)
                                # 全新的，需要播报
                                if is_new:
                                    tool_call_id = message.tool_call_id
                                    await publish_event(
                                        redis_client,
                                        run_uuid,
                                        "tool_result",
                                        {
                                            "id": tool_call_id,
                                            "tool_call_id": tool_call_id,
                                            "status": tool_status,
                                            "content": str(message.content)[:MAX_TOOL_OUTPUT_CHARS]
                                        }
                                    )
            # 根据当前的时间来进行数据落库
            now = asyncio.get_running_loop().time()
            if now - last_db_flush >= DB_THROTTLE_FLUSH_INTERVAL:
                await flush_to_db(
                    run_id=run_uuid,
                    thread_id=thread_uuid,
                    accumulator=accumulator,
                    status=MessageStatus.PENDING.value
                )
                # 更新完之后刷新时间
                last_db_flush = now
        # graph 运行完毕之后，判断是正常完毕还是因为内部发起了中断
        state = await graph.aget_state(config)
        active_interrupts = []
        for task in state.tasks:
            interrupts = getattr(task, "interrupts", None)
            if interrupts:
                active_interrupts.extend(interrupts)
        # 内部发起了中断的情况下，要获取中断数据
        # 保存到数据库，发布事件
        if active_interrupts:
            interrupt = active_interrupts[0]
            interrupt_value = getattr(interrupt, "value", {})
            # 先将中断的数据保存至中断表，同时将Run的状态改为中断态
            async with AsyncSessionWorker() as db:
                interrupt_data_dict = {
                    "run_id": run_uuid,
                    "thread_id": thread_uuid,
                    "action_type": interrupt_value.get("action_type", "clarify"),
                    "status": InterruptStatus.PENDING.value,
                    "payload": interrupt_value
                }
                new_interrupt = await interrupt_crud.create_interrupt(db, interrupt_data_dict)
                await run_crud.update_run_status(
                    db,
                    run_uuid,
                    src_status=RunStatus.IN_PROGRESS.value,
                    dest_status=RunStatus.REQUIRES_ACTION.value
                )
                await db.commit()
            await flush_to_db(
                run_id=run_uuid,
                thread_id=thread_uuid,
                accumulator=accumulator,
                status=MessageStatus.PENDING.value
            )
            await publish_event(
                redis_client,
                run_uuid,
                "requires_action",
                {
                    "interrupt_id": str(new_interrupt.id),
                    **interrupt_value
                }
            )
            return
        # 运行到这里就是没有中断，而是正常的结束了
        await flush_to_db(
            run_id=run_uuid,
            thread_id=thread_uuid,
            accumulator=accumulator,
            status=MessageStatus.SUCCESS.value
        )
        async with AsyncSessionWorker() as db:
            await run_crud.set_run_completed(db, run_uuid)
            await db.commit()
        await publish_event(
            redis_client,
            run_uuid,
            "completed",
            {}
        )
    except Exception as e:
        """
            这是运行过程中出现异常，
            那么需要将数据库中的执行状态置为failed
            还要发送事件
        """
        raise
    finally:
        await worker_lock.release()
        try:
            await redis_client.expire(stream_key, 86400)
        except Exception:
            logger.warning("Failed to expire stream: %s", stream_key)





















# async def main():
#     await rag_container.startup()
#
#     # 3. 指定会话 thread_id，用于串联前后两次请求
#     config = {"configurable": {
#         "thread_id": "session_user_1006",
#         "scope":"course",
#         "scope_id":"course_1"
#     }}
#
#     # ==========================================
#     # 阶段一：用户提问，触发 interrupt 中断
#     # ==========================================
#     print("--- 1. 发起初始提问 ---")
#     initial_input = {
#         "messages": [
#             HumanMessage(
#                 content="我想查询上次那个问题"
#             )
#         ]
#     }
#
#     # 执行图流式输出或单次调用，图在进入 ask_user_question 后会暂停
#     async for chunk in graph.astream(
#             initial_input,
#             config=config,
#             stream_mode=["messages", "updates"],
#             version="v2"
#     ):
#         chunk_type = chunk["type"]
#         data = chunk["data"]
#         if chunk_type == "messages":
#             msg_chunk: AIMessageChunk
#             msg_chunk, metadata = data
#             reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
#             content = msg_chunk.content
#             tool_chunks = msg_chunk.tool_call_chunks
#             if reasoning:
#                 print(f"  [Thinking 增量]: {repr(reasoning)}")
#             if content:
#                 print(f"  [Content 增量]: {repr(content)}")
#             if tool_chunks:
#                 print(f"  [ToolCall 增量]: {tool_chunks}")
#         # 2. updates 模式探针
#         elif chunk_type == "updates":
#             print("  [节点更新完整数据]:")
#             for node_name, node_update in data.items():
#                 print(f"    - 节点名称: {node_name}")
#                 if isinstance(node_update, dict) and "messages" in node_update:
#                     for m in node_update["messages"]:
#                         print(f"      - 输出消息类型: {type(m).__name__}")
#                         if hasattr(m, "tool_calls") and m.tool_calls:
#                             print(f"      - 完整工具调用: {m.tool_calls}")
#                         if m.additional_kwargs.get("reasoning_content"):
#                             print(
#                                 f"      - 完整思考内容: {m.additional_kwargs['reasoning_content'][:50]}..."
#                             )
#                         if m.content:
#                             print(f"      - 完整内容预览: {str(m.content)[:50]}...")
#
#
#     # 获取当前图的状态，检查是否被 interrupt 中断
#     state = await graph.aget_state(config)
#
#     if not state.tasks or not state.tasks[0].interrupts:
#         print("未触发中断，流程直接结束")
#         return
#
#     # 提取 interrupt() 中传入的字典数据（即抛给前端的渲染表单）
#     interrupt_payload = state.tasks[0].interrupts[0].value
#     print("\n--- 2. 捕获到 Interrupt 事件 ---")
#     print(f"Action Type: {interrupt_payload.get('action_type')}")
#     print("下发给前端的表单数据：")
#     print(interrupt_payload)
#
#
#     # ==========================================
#     # 阶段二：模拟前端提交表单，通过 Command 恢复
#     # ==========================================
#     # 模拟前端收集到用户选择后的提交格式
#     frontend_submission = [
#         {"id": "previous_question", "selected": "我是想问Transformer预测下一个词是否是由当前输入的最后一个词主要来决定呢(重要)"},
#     ]
#
#     print("\n--- 3. 模拟前端回复并恢复图执行 ---")
#     # 通过 Command(resume=...) 传入用户数据
#     # 这个值会直接作为 ask_user_question 内部 interrupt(...) 的返回值！
#     async for chunk in graph.astream(
#             Command(resume=frontend_submission),
#             config=config,
#             stream_mode=["messages", "updates"],
#             version="v2"
#     ):
#         chunk_type = chunk["type"]
#         data = chunk["data"]
#         if chunk_type == "messages":
#             msg_chunk: AIMessageChunk
#             msg_chunk, metadata = data
#             # 1. 如果是 LLM 生成的 Chunk
#             if isinstance(msg_chunk, AIMessageChunk):
#                 reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
#                 content = msg_chunk.content
#                 tool_chunks = msg_chunk.tool_call_chunks
#                 if reasoning:
#                     print(f"  [Thinking 增量]: {repr(reasoning)}")
#                 if content:
#                     print(f"  [Content 增量]: {repr(content)}")
#                 if tool_chunks:
#                     print(f"  [ToolCall 增量]: {tool_chunks}")
#             # 2. 如果是 Tool 节点返回的消息
#             elif isinstance(msg_chunk, ToolMessage):
#                 print(f"  [ToolMessage 结果 (id={msg_chunk.tool_call_id})]: {msg_chunk.content}")
#         # 2. updates 模式探针
#         elif chunk_type == "updates":
#             print("  [节点更新完整数据]:")
#             for node_name, node_update in data.items():
#                 print(f"    - 节点名称: {node_name}")
#                 if isinstance(node_update, dict) and "messages" in node_update:
#                     for m in node_update["messages"]:
#                         print(f"      - 输出消息类型: {type(m).__name__}")
#                         if hasattr(m, "tool_calls") and m.tool_calls:
#                             print(f"      - 完整工具调用: {m.tool_calls}")
#                         if m.additional_kwargs.get("reasoning_content"):
#                             print(
#                                 f"      - 完整思考内容: {m.additional_kwargs['reasoning_content'][:50]}..."
#                             )
#                         if m.content:
#                             print(f"      - 完整内容预览: {str(m.content)}...")
#
#     await rag_container.shutdown()
# if __name__ == "__main__":
#     asyncio.run(main())