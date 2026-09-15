import asyncio
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, ToolCall, ToolMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import BaseTool
from langgraph.constants import END
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langgraph.graph import add_messages, StateGraph, START, END
from app.core.config import settings
# 导入上一节中定义的工具
from app.rag_agent.tools import ask_user_question, search
from pydantic import BaseModel
from typing import Annotated, TypedDict
from langgraph.config import RunnableConfig
from app.core.rag_deps import rag_container

tools = [search, ask_user_question]
tool_handler = {tool.name: tool for tool in tools}
model = ChatDeepSeek(
    model_name=settings.model_name,
    api_key=settings.api_key,
    base_url=settings.base_url
)
model_with_tools = model.bind_tools(tools)


class OverAllState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


async def tool_node(state: OverAllState, config: RunnableConfig):
    last_message: AIMessage = state["messages"][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool: BaseTool = tool_handler.get(tool_call["name"])
        tool_result = await tool.ainvoke(tool_call["args"], config) if tool else f"Unknown tool: {tool_call['name']}"
        tool_messages.append(
            ToolMessage(
                tool_call_id=tool_call["id"],
                content=tool_result
            )
        )
    return {"messages": tool_messages}


async def call_model(state: OverAllState, config: RunnableConfig):
    messages = state["messages"]
    response = await model_with_tools.ainvoke(messages, config)
    return {"messages": [response]}


async def should_continue(state: OverAllState):
    messages = state["messages"]
    last_message: AIMessage = messages[-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


graph_builder = StateGraph(state_schema=OverAllState)
graph_builder.add_node("call_model", call_model)
graph_builder.add_node("tool_node", tool_node)
graph_builder.add_edge(START, "call_model")
graph_builder.add_edge("tool_node", "call_model")
graph_builder.add_conditional_edges("call_model", should_continue)
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)


async def main():
    await rag_container.startup()

    # 3. 指定会话 thread_id，用于串联前后两次请求
    config = {"configurable": {
        "thread_id": "session_user_1006",
        "scope": "course",
        "scope_id": "course_1"
    }}

    # ==========================================
    # 阶段一：用户提问，触发 interrupt 中断
    # ==========================================
    print("--- 1. 发起初始提问 ---")
    initial_input = {
        "messages": [
            HumanMessage(
                content="我想查询上次那个问题"
            )
        ]
    }

    # 执行图流式输出或单次调用，图在进入 ask_user_question 后会暂停
    async for chunk in graph.astream(
            initial_input,
            config=config,
            stream_mode=["messages", "updates"],
            version="v2"
    ):
        chunk_type = chunk["type"]
        data = chunk["data"]
        if chunk_type == "messages":
            msg_chunk: AIMessageChunk
            msg_chunk, metadata = data
            reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
            content = msg_chunk.content
            tool_chunks = msg_chunk.tool_call_chunks
            if reasoning:
                print(f"  [Thinking 增量]: {repr(reasoning)}")
            if content:
                print(f"  [Content 增量]: {repr(content)}")
            if tool_chunks:
                print(f"  [ToolCall 增量]: {tool_chunks}")
        # 2. updates 模式探针
        elif chunk_type == "updates":
            print("  [节点更新完整数据]:")
            for node_name, node_update in data.items():
                print(f"    - 节点名称: {node_name}")
                if isinstance(node_update, dict) and "messages" in node_update:
                    for m in node_update["messages"]:
                        print(f"      - 输出消息类型: {type(m).__name__}")
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            print(f"      - 完整工具调用: {m.tool_calls}")
                        if m.additional_kwargs.get("reasoning_content"):
                            print(
                                f"      - 完整思考内容: {m.additional_kwargs['reasoning_content'][:50]}..."
                            )
                        if m.content:
                            print(f"      - 完整内容预览: {str(m.content)[:50]}...")

    # 获取当前图的状态，检查是否被 interrupt 中断
    state = await graph.aget_state(config)

    if not state.tasks or not state.tasks[0].interrupts:
        print("未触发中断，流程直接结束")
        return

    # 提取 interrupt() 中传入的字典数据（即抛给前端的渲染表单）
    interrupt_payload = state.tasks[0].interrupts[0].value
    print("\n--- 2. 捕获到 Interrupt 事件 ---")
    print(f"Action Type: {interrupt_payload.get('action_type')}")
    print("下发给前端的表单数据：")
    print(interrupt_payload)

    # ==========================================
    # 阶段二：模拟前端提交表单，通过 Command 恢复
    # ==========================================
    # 模拟前端收集到用户选择后的提交格式
    frontend_submission = [
        {"id": "previous_question", "selected": "我是想问alias的作用"},
    ]

    print("\n--- 3. 模拟前端回复并恢复图执行 ---")
    # 通过 Command(resume=...) 传入用户数据
    # 这个值会直接作为 ask_user_question 内部 interrupt(...) 的返回值！
    async for chunk in graph.astream(
            Command(resume=frontend_submission),
            config=config,
            stream_mode=["messages", "updates"],
            version="v2"
    ):
        chunk_type = chunk["type"]
        data = chunk["data"]
        if chunk_type == "messages":
            msg_chunk: AIMessageChunk
            msg_chunk, metadata = data
            # 1. 如果是 LLM 生成的 Chunk
            if isinstance(msg_chunk, AIMessageChunk):
                reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
                content = msg_chunk.content
                tool_chunks = msg_chunk.tool_call_chunks
                if reasoning:
                    print(f"  [Thinking 增量]: {repr(reasoning)}")
                if content:
                    print(f"  [Content 增量]: {repr(content)}")
                if tool_chunks:
                    print(f"  [ToolCall 增量]: {tool_chunks}")
            # 2. 如果是 Tool 节点返回的消息
            elif isinstance(msg_chunk, ToolMessage):
                print(f"  [ToolMessage 结果 (id={msg_chunk.tool_call_id})]: {msg_chunk.content}")
        # 2. updates 模式探针
        elif chunk_type == "updates":
            print("  [节点更新完整数据]:")
            for node_name, node_update in data.items():
                print(f"    - 节点名称: {node_name}")
                if isinstance(node_update, dict) and "messages" in node_update:
                    for m in node_update["messages"]:
                        print(f"      - 输出消息类型: {type(m).__name__}")
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            print(f"      - 完整工具调用: {m.tool_calls}")
                        if m.additional_kwargs.get("reasoning_content"):
                            print(
                                f"      - 完整思考内容: {m.additional_kwargs['reasoning_content'][:50]}..."
                            )
                        if m.content:
                            print(f"      - 完整内容预览: {str(m.content)}...")

    await rag_container.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
