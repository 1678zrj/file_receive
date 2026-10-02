from langgraph.config import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage, ToolCall
from langchain_core.tools import BaseTool
from app.rag_agent.state import OverAllState
from app.rag_agent.tool_registry import tool_registry
from pydantic import ValidationError


async def gate_dispatcher_node(state: OverAllState, config: RunnableConfig):
    """
    中央调度门禁
    先对当前的所以工具调用统一进行格式校验，若检测到工具调用存在格式问题的，
    直接填补所有工具调用消息，并返回到agent节点
    使用 groupby 根据tool的 ToolAction 类型进行切片
    - 连续的read 聚合为 read_batch(并发)
    - 连续的write 拆分为单个single_write （单步审批+独立事务）
    - 连续的interactive拆分为单个 interactive
    """
    last_message: AIMessage = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    if not tool_calls:
        pass