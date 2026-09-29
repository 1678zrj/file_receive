from langgraph.config import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage, ToolCall
from langchain_core.tools import BaseTool
from app.rag_agent.state import OverAllState
from app.rag_agent.tool_registry import tool_registry
from pydantic import ValidationError






def build_validation_error_tool_result(
        e: ValidationError
) -> str:


    pass






async def tool_node(state: OverAllState, config: RunnableConfig):
    last_message: AIMessage = state["messages"][-1]
    tool_messages = []
    configurable = config.get("configurable", {})
    user_role = configurable.get("user_role")
    tool_handler = tool_registry.get_role_tools_handler(role=user_role)
    for tool_call in last_message.tool_calls:
        status = "success"
        tool: BaseTool = tool_handler.get(tool_call["name"])
        if not tool:
            tool_result = f"Unknown tool: {tool_call['name']}"
            status = "error"
        else:
            try:
                tool_result = await tool.ainvoke(tool_call["args"], config)
            except ValidationError as e:
                tool_result = build_validation_error_tool_result(e)
                status = "error"
        tool_messages.append(
            ToolMessage(
                tool_call_id=tool_call["id"],
                content=tool_result,
                status=status
            )
        )
    return {"messages": tool_messages}