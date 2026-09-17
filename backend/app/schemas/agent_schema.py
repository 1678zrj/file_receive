import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from typing import Any

class ThreadCreateRequest(BaseModel):
    title: str = Field(
        default="新会话",
        min_length=1,
        max_length=255
    )

class ThreadCreateResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str




class RunCreateRequest(BaseModel):
    # 用户的输入
    prompt: str = Field(
        min_length=1,
        max_length=100000
    )
    scope: str = Field(
        min_length=1,
        max_length=32,
    )
    scope_id: str = Field(
        min_length=1,
        max_length=64
    )
    # 必填
    #
    # 客户端每次发起一次"创建 Run"请求,
    # 都应该生成一个新的 idempotency_key
    # 如果请求因为网络原因重试
    # 则必须复用同一个 key
    idempotency_key: str = Field(
        min_length=1,
        max_length=128
    )


class RunCreateResponse(BaseModel):
    thread_id: uuid.UUID
    run_id: uuid.UUID
    status: str
    stream_url: str


class ResumeRequest(BaseModel):
    resolution: list[dict[str, Any]] | dict[str, Any] | Any

class ResumeResponse(BaseModel):
    thread_id: uuid.UUID
    run_id: uuid.UUID
    status: str

class SingleThreadResponse(BaseModel):
    id: uuid.UUID
    user_id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
class ListThreadResponse(BaseModel):
    threads: list[SingleThreadResponse]

class SingleMessageResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    role: str
    content: str
    parts: list[dict[str, Any]] | None
    tool_calls: list[dict[str, Any]] | None
    citations: list[dict[str, Any]] | None
    status: str
    created_at: datetime
    resolved_at: datetime | None

class ThreadMessageResponse(BaseModel):
    messages: list[SingleMessageResponse]