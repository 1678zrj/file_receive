import asyncio
import json
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langgraph.prebuilt import create_react_agent
from app.core.config import settings


@tool
def get_weather(location: str) -> str:
    """获取指定城市的天气预报。"""
    return f"{location}今天晴朗，23°C"


async def main():
    model = ChatDeepSeek(
        base_url=settings.base_url,
        model=settings.model_name,
        api_key=settings.api_key,
    )

    # 构建简单的 ReAct 图进行测试
    agent = create_react_agent(model, tools=[get_weather])

    inputs = {"messages": [HumanMessage(content="查询北京今天的天气，并根据天气给出一句建议。")]}

    print("================ 开始 astream(version='v2') 探针测试 ================\n")

    step = 0
    async for chunk in agent.astream(
            inputs,
            stream_mode=["messages", "updates"],
            version="v2",
    ):
        step += 1
        chunk_type = chunk["type"]
        data = chunk["data"]

        print(f"\n--- [Step {step}] chunk['type'] = '{chunk_type}' ---")

        # 1. messages 模式探针
        if chunk_type == "messages":
            # data 是二元组：(MessageChunk, metadata)
            msg_chunk, metadata = data
            node = metadata.get("langgraph_node", "unknown")

            # 检查思考链
            reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
            # 检查正文
            content = msg_chunk.content
            # 检查工具调用分块
            tool_chunks = getattr(msg_chunk, "tool_call_chunks", [])

            print(f"  [来源节点]: {node}")
            print(f"  [Chunk 类型]: {type(msg_chunk).__name__}")
            if reasoning:
                print(f"  [Thinking 增量]: {repr(reasoning)}")
            if content:
                print(f"  [Content 增量]: {repr(content)}")
            if tool_chunks:
                print(f"  [ToolCall 增量]: {tool_chunks}")

        # 2. updates 模式探针
        elif chunk_type == "updates":
            # data 是字典：{node_name: state_update}
            print(f"  [节点更新完整数据]:")
            for node_name, node_update in data.items():
                print(f"    - 节点名称: {node_name}")
                if isinstance(node_update, dict) and "messages" in node_update:
                    for m in node_update["messages"]:
                        print(f"      - 输出消息类型: {type(m).__name__}")
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            print(f"      - 完整工具调用: {m.tool_calls}")
                        if m.additional_kwargs.get("reasoning_content"):
                            print(f"      - 完整思考内容: {m.additional_kwargs['reasoning_content'][:50]}...")
                        if m.content:
                            print(f"      - 完整内容预览: {str(m.content)[:50]}...")

    print("\n================ 测试结束 ================")


if __name__ == "__main__":
    asyncio.run(main())