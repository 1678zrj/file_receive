import asyncio

from langgraph.config import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage, ToolCall
from langchain_core.tools import BaseTool, StructuredTool
from itertools import groupby

from langgraph.errors import GraphInterrupt, NodeInterrupt

from app.rag_agent.schema import ToolAction
from app.rag_agent.state import OverAllState
from app.rag_agent.tool_registry import tool_registry
from langgraph.graph import END
from typing import Any
from pydantic import ValidationError
from langchain_core.tools import ToolException

def drain_remaining_tasks_as_cancelled(
        remaining_tasks: list[dict[str, Any]]
) -> list[ToolMessage]:
    cancelled_tool_messages: list[ToolMessage] = []
    for task in remaining_tasks:
        task_type = task["type"]
        cancelled_tool_calls: list[ToolCall] = task["calls"] if task_type == "read_batch" else [task["call"]]
        for cancelled_tool_call in cancelled_tool_calls:
            cancelled_tool_messages.append(
                ToolMessage(
                    tool_call_id=cancelled_tool_call["id"],
                    content="Cancelled: Execution aborted because preceding tool.",
                    name=cancelled_tool_call["name"],
                    status="error"
                )
            )
    return cancelled_tool_messages

def resolve_task_category(tool_name: str) -> str:
    tool = tool_registry.get_tool_by_name(tool_name)
    meta_data = tool.metadata
    tool_action = meta_data.get("tool_action")
    if tool_action == ToolAction.READ.value:
        return "read_batch"
    elif tool_action == ToolAction.INTERACTIVE.value:
        return "interactive"
    elif tool_action == ToolAction.WRITE.value:
        return "single_write"


def prefilght_validate_calls(
        tool_calls: list[ToolCall],
        user_role: int
) -> tuple[bool, list[ToolMessage]]:
    """
    静态工具预检（带 RBAC 深度防御）
    检验工具注册、角色执行权限与参数schema
    """
    # key是tool_call_id，标明工具对应的问题
    validation_errors: dict[str, str] = {}
    call_map: dict[str, dict[str, Any]] = {}
    # 先遍历所有的工具调用
    for tool_call in tool_calls:
        # 对每个工具调用，先校验存在权限问题，权限没问题再检验格式问题
        tool_call_id = tool_call["id"]
        tool_call_args = tool_call["args"]
        tool_call_name = tool_call["name"]
        call_map[tool_call_id] = tool_call
        # 工具是否存在
        tool = tool_registry.get_tool_by_name(tool_call_name)
        if not tool:
            validation_errors[tool_call_id] = f"Tool [{tool_call_name}] is not registered in system."
            continue
        # 工具权限是否通过
        tool = tool_registry.get_tool_by_name_and_role(tool_call_name, user_role)
        if not tool:
            validation_errors[tool_call_id] = f"Permission denied: role [{user_role}] cannot execute [{tool_call_name}]."
            continue
        # 工具存在且权限检验通过，检查格式是否正确
        try:
            tool.args_schema.model_validate(tool_call_args)
        except ValidationError as e:
            validation_errors[tool_call_id] = f"Parameter schema validation failed: {e.errors()}"
        except Exception as e:
            validation_errors[tool_call_id] = f"Argument validation encountered unexpected error: {str(e)}"
    # validation_error为空，工具调用可正常进行
    if not validation_errors:

        return True, []
    # 如果validation_error不为空，当前轮次的工具调用完全取消
    # 仍要填补tool_messafe
    # 预检未通过，全量合成拒绝与撤销消息，避免悬空 ID
    synthetic_messages: list[ToolMessage] = []
    failing_tool_names = [call_map[cid]["name"] for cid in validation_errors]
    failing_summary = ", ".join(set(failing_tool_names))

    for call in tool_calls:
        call_id = call["id"]
        tool_name = call["name"]
        if call_id in validation_errors:
            synthetic_messages.append(
                ToolMessage(
                    content=f"Error: Tool [{tool_name}] {validation_errors[call_id]}",
                    tool_call_id=call_id,
                    name=tool_name,
                    status="error"
                )
            )
        else:
            synthetic_messages.append(
                ToolMessage(
                    content=f"Cancelled: Batch preflight validation aborted because tool(s) [{failing_summary}] failed validation.",
                    tool_call_id=call_id,
                    name=tool_name,
                    status="error"
                )
            )

    return False, synthetic_messages




async def gate_dispatcher_node(state: OverAllState, config: RunnableConfig):
    """
    中央调度门禁
    先对当前的所以工具调用统一进行格式校验，若检测到工具调用存在格式问题的，
    直接填补所有工具调用消息，并返回到agent节点
    还有对所有工具进行权限校验，看是否被提示词注入调用了不该调用的工具
    使用 groupby 根据tool的 ToolAction 类型进行切片
    - 连续的read 聚合为 read_batch(并发)
    - 连续的write 拆分为单个single_write （单步审批+独立事务）
    - 连续的interactive拆分为单个 interactive
    """
    last_message: AIMessage = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    invalid_tool_calls = getattr(last_message, "invalid_tool_calls", [])
    # 如果模型输出的工具调用有的甚至不符合JSON格式
    if invalid_tool_calls:
        error_messages: list[ToolMessage] = []
        for ic in invalid_tool_calls:
            error_messages.append(
                ToolMessage(
                    tool_call_id=ic["id"],
                    content=f"Error: Failed to parse tool call arguments: {ic.get('error', 'Malformed JSON')}",
                    name=ic["name"],
                    status="error"
                )
            )
        for tc in tool_calls:
            error_messages.append(
                ToolMessage(
                    tool_call_id=tc["id"],
                    content="Cancelled: Tool execution aborted due to malformed tool call in parallel batch.",
                    name=tc["name"],
                    status="error"
                )
            )
        return {
            "messages": error_messages,
            "pending_tasks": []
        }
    # 模型输出的都是有效JSON格式（但不一定符合pydantic格式约束）的工具调用
    # 接下来进行工具的pydantic格式及权限校验
    configurable = config.get("configurable", {})
    user_role = configurable.get("user_role")
    # 进入校验函数
    is_valid, repaired_messages = prefilght_validate_calls(tool_calls, user_role)
    if not is_valid:
        return {
            "messages": repaired_messages,
            "pending_tasks": []
        }
    # 通过格式与权限校验后，可以对并行工具调用进行分片了
    tasks = []
    for category, group in groupby(tool_calls, key=lambda tool_call: resolve_task_category(tool_call["name"])):
        group_calls = list(group)
        if category == "read_batch":
            tasks.append(
                {"type": "read_batch", "calls": group_calls}
            )
        elif category == "single_write":
            for call in group_calls:
                tasks.append(
                    {"type": "single_write", "call": call}
                )
        elif category == "interactive":
            for call in group_calls:
                tasks.append(
                    {"type": "interactive", "call": call}
                )
    print(f"切片后的工具调用是：{tasks}")
    # 已经分好类了，可以按照批次进入对应的节点执行
    return {"pending_tasks": tasks}

async def execute_read_tool(tool_call: ToolCall, config: RunnableConfig) -> ToolMessage:
    tool: BaseTool = tool_registry.get_tool_by_name(tool_call["name"])
    try:
        result = await tool.ainvoke(tool_call["args"], config)
        tool_message = ToolMessage(
            tool_call_id=tool_call["id"],
            content=result,
            name=tool_call["name"],
            status="success"
        )
    # 捕获工具内部抛出的异常
    except ToolException as e:
        tool_message = ToolMessage(
            tool_call_id=tool_call["id"],
            content=str(e),
            name=tool_call["name"],
            status="error"
        )
    # 全局异常捕获兜底
    except Exception as e:
        tool_message = ToolMessage(
            tool_call_id=tool_call["id"],
            content=str(e),
            name=tool_call["name"],
            status="error"
        )
    return tool_message


async def read_batch_node(state: OverAllState, config: RunnableConfig):
    print("进入read_batch_node")
    tasks = list(state.get("pending_tasks", []))
    # 获取当前要执行的一批工具调用
    current_task = tasks[0]
    remaining_tasks = tasks[1:]
    read_tool_calls = current_task.get("calls", [])
    tasks_group = [execute_read_tool(read_tool_call, config) for read_tool_call in read_tool_calls]
    results: list[ToolMessage] = await asyncio.gather(*tasks_group)
    if any(tool_message.status == "error" for tool_message in results) and remaining_tasks:
        canceled_messages = drain_remaining_tasks_as_cancelled(remaining_tasks)
        return {
            "messages": results + canceled_messages,
            "pending_tasks": []
        }
    return {
        "messages": results,
        "pending_tasks": remaining_tasks
    }

async def interactive_node(state: OverAllState, config: RunnableConfig):
    tasks = list(state.get("pending_tasks", []))
    # 获取当前要执行的一批工具调用
    current_task = tasks[0]
    remaining_tasks = tasks[1:]
    interactive_tool_call = current_task.get("call")
    try:
        tool: BaseTool = tool_registry.get_tool_by_name(interactive_tool_call["name"])
        result = await tool.ainvoke(interactive_tool_call["args"], config)
        interactive_tool_message = ToolMessage(
            tool_call_id=interactive_tool_call["id"],
            content=result,
            name=interactive_tool_call["name"],
            status="success"
        )
        return {
            "messages": [interactive_tool_message],
            "pending_tasks": remaining_tasks
        }
    except (GraphInterrupt, NodeInterrupt) as e:
        raise
    except ToolException as e:
        tool_message = ToolMessage(
            tool_call_id=interactive_tool_call["id"],
            content=str(e),
            name=interactive_tool_call["name"],
            status="error"
        )
    except Exception as e:
        tool_message = ToolMessage(
            tool_call_id=interactive_tool_call["id"],
            content=str(e),
            name=interactive_tool_call["name"],
            status="error"
        )
    canceled_messages = drain_remaining_tasks_as_cancelled(remaining_tasks)
    return {
        "messages": [tool_message] + canceled_messages,
        "pending_tasks": []
    }
# 该函数作为核心中转站条件边的判断函数非常重要
# 会和很多节点相连，如gate_dispatcher_node、read_batch_node、
# single_write_node、interactive_node、END
async def router_next_task(state: OverAllState):
    # 当出现致命错误（在工具调用中概率极小，甚至没有）
    if state.get("fatal_error"):
        return END
    # 查看是否还有未完成的工具调用
    pending_tasks = state.get("pending_tasks", [])
    # 没有的情况，说明1、工具调用执行完毕 2、执行出错后被ToolMessage被自动填补
    # 返回到获取模型响应的节点
    if not pending_tasks:
        return "call_model"
    # 仍有未完成的工具调用，获取工具调用的具体类型，
    # 根据类型路由到对应的节点
    next_task_type = pending_tasks[0]["type"]
    if next_task_type == "read_batch":
        return "read_batch_node"
    elif next_task_type == "single_write":
        return "single_write_node"
    elif next_task_type == "interactive":
        return "interactive_node"
    # 兜底，理论上不会运行到这里，或者说运行到这里的话，
    # 应该就是仍然存在工具调用，但是工具调用的type没有被前面的条件判断碰上
    # 那么理论上去call_model节点会报错
    return "call_model"





