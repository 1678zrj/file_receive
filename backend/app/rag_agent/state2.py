from typing import TypedDict, Annotated, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages



class OverAllState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    pending_tasks: list[dict[str, Any]]
    fatal_error: dict[str, Any] | None  # 记录不可逆异常，驱动图流转至END