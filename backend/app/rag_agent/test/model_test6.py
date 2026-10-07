import asyncio
import json
from typing import Literal
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END, START, MessagesState, StateGraph
from app.core.config import settings


# 1. 定义工具
@tool
def get_weather(location: str) -> str:
    """获取指定城市的天气预报。"""
    mock_db = {"北京": "晴朗 23°C", "上海": "多云 25°C"}
    return mock_db.get(location, "晴 24°C")


tools = [get_weather]
tools_by_name = {t.name: t for t in tools}

# 2. 初始化模型
model = ChatDeepSeek(
    base_url=settings.base_url,
    model=settings.model_name,
    api_key=settings.api_key,
)
model_with_tools = model.bind_tools(tools)


# 3. 自定义 Agent 节点：保留 reasoning_content 的核心
async def call_model_node(state: MessagesState) -> dict:
    """调用大模型并确保思考链字段完整回填到 State 中"""
    messages = state["messages"]

    # 原生 ainvoke 返回的 response 已经包含完整 additional_kwargs
    response: AIMessage = await model_with_tools.ainvoke(messages)

    # 防御性补丁：防止某些第三方代理在未思考时漏传 reasoning_content 导致下轮报错
    if "reasoning_content" not in response.additional_kwargs:
        response.additional_kwargs["reasoning_content"] = ""

    # 直接返回原生对象，add_messages 机制会自动将其追加到全局状态，元数据无损保留
    return {"messages": [response]}


# 4. 自定义 Tool 节点（不使用官方 prebuilt ToolNode）
async def call_tools_node(state: MessagesState) -> dict:
    """手动执行工具调用并生成 ToolMessage"""
    last_message = state["messages"][-1]
    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        # 执行工具
        tool = tools_by_name[tool_name]
        tool_output = await tool.ainvoke(tool_args)

        tool_messages.append(
            ToolMessage(
                content=str(tool_output),
                tool_call_id=tool_id,
            )
        )

    return {"messages": tool_messages}


# 5. 条件路由逻辑
def should_continue(state: MessagesState) -> Literal["tools", END]:
    last_message = state["messages"][-1]
    # 判断是否存在未处理的工具调用
    if last_message.tool_calls:
        return "tools"
    return END


# 6. 构建 Graph
workflow = StateGraph(MessagesState)

workflow.add_node("agent", call_model_node)
workflow.add_node("tools", call_tools_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, ["tools", END])
workflow.add_edge("tools", "agent")

app = workflow.compile()


# 7. 运行与流式消费验证
async def main():
    inputs = {"messages": [("user", "上海的天气怎么样？")]}

    # 流式读取输出（LangGraph 会自动从自定义节点的 ainvoke 中捕获 chunk 流）
    async for chunk, metadata in app.astream(inputs, stream_mode="messages"):
        node = metadata.get("langgraph_node")

        if node == "agent":
            # 流式提取思考链
            reasoning = chunk.additional_kwargs.get("reasoning_content", "")
            if reasoning:
                print(reasoning, end="", flush=True)

            # 流式提取回答正文
            if chunk.content:
                print(chunk.content, end="", flush=True)

        elif node == "tools":
            print(f"\n[自定义工具节点执行结果]: {chunk.content}\n")


if __name__ == "__main__":
    asyncio.run(main())