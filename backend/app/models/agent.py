import enum
from typing import Any

from sqlalchemy import Column, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Index
from app.models.base import utc_now, AwareCreatedAt, AwareUpdatedAt, AwareNullableDateTime
import uuid


# 一个用户可以有多个会话窗口
# class Thread(SQLModel, table=True):
#     __tablename__ = "thread"
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, description="可对应langgraph的thread_id")
#     user_id: int = Field(index=True)
#     title: str = Field(default="新会话", max_length=255)
#     status: str = Field(description="active", index=True)
#     scope: str = Field(index=True, max_length=32)
#     scope_id: str = Field(index=True, max_length=64)
#     created_at: AwareCreatedAt
#     updated_at: AwareUpdatedAt
#
#     __table_args__ = (
#         Index("idx_threads_user_created", "user_id", "created_at"),
#         Index("idx_threads_scope", "scope", "scope_id")
#     )

class ThreadStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    REQUIRES_ACTION = "requires_action"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"

class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

class InterruptStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    CANCELED = "canceled"



"""
    对于Agent问答数据库设计，有很多思路需要理清楚
    目的：Thread会话中可以有多个Run记录（包括以前运行和现在活跃的）
        而活跃的Run(即正在运行的)只能有一个，这是根本
        活跃的Run的状态定义是QUEUED、IN_PROGRESS、REQUIRES_ACTION
        通过PostgreSql的部分唯一索引确保Run表中同一thread对应的Run只有一个是活跃状态
    操作：用户要恢复某个Thread中处于REQUIRES_ACTION中断状态的Run，
        那么这个Run应该是存在于Run表中，可以通过Thread_id和Run_id找到（虽然Run_id本就是唯一，但配上Thread_id更加稳妥）
        所以请求中应该带上thread_id、run_id，还有用户恢复中断带有的数据
        且Run的状态应该是REQUIRES_ACTION状态
        可能会出现几个竞争状态
        1、用户要恢复的Thread的Run错了，不存在、或者状态不对
        2、用户要恢复的Thread的Run是对的，但是重复请求了，那么为了防止worker被重复投递
        3、用户此时还要发出新的请求开启新的Run（这应该是交给创建Run的API来处理，这里讨论的是恢复中断的API）
        对于问题1，可以通过获取和鉴权，判断该run是否存在，状态是否正确
        对于问题2、3，可以先加上Redis分布式锁，锁的粒度应该是Thread级别
        锁住当前的Thread，这样一来，不管是2的重复请求还是3的新建Run，都要先抢到执行权，抢到执行权后再进行校验
        3的话对于创建Run的API有要求，即若已有活跃状态的其它Run，则要立刻释放锁
        2的话就是对于恢复Run的API有要求，也是先抢锁
        然后先check then act校验，查看当前要操作的Run是否还是处于REQUIRES_ACTION状态
        不是的话说明已经被其它请求抢先修改了，返回
        考虑到Redis分布式锁和check then act校验都不够可靠，需要数据库进行兜底。
        这里的兜底采用的是状态机乐观锁，想像两个同时执行的请求，越过了分布式锁、check then act校验也通过
        那就需要乐观锁兜底了，通过update run set status = "queued" where status = "REQUIRES_ACTION"
        执行该语句并查看更新的行数，成功更新的抢到执行权，没更新的退出
        成功更新的开始进行相关数据库操作和任务投递
"""

class Thread(SQLModel, table=True):
    """
    Agent会话
    Thread 表示一段长期存在的对话容器。
    它不绑定具体知识库， 具体知识库由 Run 绑定。
    因为同一个 Thread 中 可以有多个Run
    这样一来就可以使用不同的知识库 / 数据域
    """
    __tablename__ = "thread"
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="可对应langgraph的thread_id"
    )
    user_id: int = Field(index=True)
    title: str = Field(default="新会话", max_length=255)
    status: str = Field(description="active", index=True)
    # 新增修改，对比原版，将scope和scope_id移除，下放至Run，即每一轮问答都可以自由切换知识库
    created_at: AwareCreatedAt
    updated_at: AwareUpdatedAt

    __table_args__ = (
        Index("idx_threads_user_created", "user_id", "created_at"),
    )


# 一个会话窗口可以有多轮对话
class Run(SQLModel, table=True):
    """
    Agent 的一次具体执行
    scope / scope_id 属于 Run, 而不是 Thread
    原因：
        一个 Thread 可以连续产生多个 Run
        每个 Run 可以选择不同的知识库
    例如：
        Thread T1
            Run R1 -> KB-A
            Run R2 -> KB-B
            Run R3 -> KB-A
    """

    __tablename__ = "run"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 当前运行和会话窗口关联
    thread_id: uuid.UUID = Field(foreign_key="thread.id", index=True)
    idempotency_key: str | None = Field(default=None, max_length=128, index=True)
    user_id: int = Field(index=True)
    # 本次Run使用的 数据域 / 知识库
    scope: str = Field(index=True, max_length=32)
    scope_id: str = Field(index=True, max_length=64)
    # 运行状态，有queued / in_progress / requires_action / completed / failed / cancelled
    status: str = Field(default="queued", index=True)
    trigger_type: str = Field(default="user_prompt", max_length=32)
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = None
    token_usage: dict[str, Any] = Field(default=None, sa_column=Column(JSONB))
    created_at: AwareCreatedAt
    started_at: AwareNullableDateTime = None
    finished_at: AwareNullableDateTime = None
    # 用户进行一次run的请求面临两层并发安全
    # 1、同一幂等键请求的并发重复
    # 2、不同幂等键请求的并发重复
    __table_args__ = (
        Index("idx_runs_thread_status", "thread_id", "status"),
        Index("idx_runs_scope", "scope", "scope_id"),
        # 幂等唯一约束。
        #
        # 同一个用户：
        # idempotency_key = X
        #
        # 只能对应一个 Run。
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_runs_user_idempotency_key",
        ),

        # 一个 Thread 同一时间最多允许一个 active Run。
        #
        # 这是最终 DB 兜底。
        #
        # Redis thread lock 用于降低并发冲突，
        # DB partial unique index 用于保证最终正确性。
        Index(
            "uq_active_run_per_thread",
            "thread_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'in_progress', 'requires_action')"
            ),
        ),
    )


# 一轮对话也只对应一个Message
class Message(SQLModel, table=True):
    __tablename__ = "message"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    thread_id: uuid.UUID = Field(foreign_key="thread.id", index=True)
    run_id: uuid.UUID | None = Field(default=None, foreign_key="run.id", index=True)
    role: str = Field(max_length=32)  # user / assistant / system
    content: str = Field(default="")

    # 高保真时序块
    parts: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))
    tool_calls: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))
    citations: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))
    # in_progress / requires_action / success / failed / cancelled
    status: str = Field(default="success", max_length=32)
    created_at: AwareCreatedAt
    resolved_at: AwareNullableDateTime = None
    __table_args__ = (
        Index("idx_messages_thread_created", "thread_id", "created_at"),
    )


class Interrupt(SQLModel, table=True):
    __tablename__ = "interrupt"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    thread_id: uuid.UUID = Field(foreign_key="thread.id", index=True)
    run_id: uuid.UUID | None = Field(default=None, foreign_key="run.id", index=True)
    # 默认是clarify类型，但是还兼容其它类型，以备后续扩展
    action_type: str = Field(default="clarify", max_length=64)
    status: str = Field(default="pending", max_length=32)
    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    resolution: dict[str, Any] = Field(default=None, sa_column=Column(JSONB))
    resolved_by: int | None = Field(default=None)
    created_at: AwareCreatedAt
    resolved_at: AwareNullableDateTime = None
    # 一个 Run 同一时间只能有一个Pending Interrupt
    __table_args__ = (
        Index("uq_pending_interrupt_per_run", "run_id", unique=True, postgresql_where=text("status = 'pending'")),
        Index("idx_interrupts_thread_status", "thread_id", "status"),
    )
