import asyncio
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from app.core.config import settings


@tool
def get_weather(location: str) -> str:
    """获取指定城市的天气预报。"""
    mock_db = {
        "北京": "北京今天晴朗，23°C",
        "上海": "上海多云转阴，25°C",
        "广州": "广州雷阵雨，30°C",
    }
    return mock_db.get(location, f"{location}今天晴朗，24°C")


async def main():
    model = ChatDeepSeek(
        base_url=settings.base_url,
        model=settings.model_name,
        api_key=settings.api_key,
        extra_body={"thinking": {"type": "disabled"}}
    )

    # 1. 引入 MemorySaver 检查点，模拟生产环境的 checkpointer
    checkpointer = MemorySaver()
    agent = create_react_agent(model, tools=[get_weather], checkpointer=checkpointer)

    # 2. 指定固定的 thread_id 维持多轮记忆上下文
    config = {"configurable": {"thread_id": "test_probe_thread_001"}}

    print("================ 开始 astream(version='v2') 多轮探针测试 ================")
    print("支持连续追问（例如输入：'北京天气' -> '那上海呢？' -> '对比一下两地气温'）")
    print("输入 exit 或 quit 退出\n")

    turn_count = 0

    while True:
        user_input = await asyncio.to_thread(input, "\nUser: ")
        user_input = user_input.strip()

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("测试结束。")
            break

        turn_count += 1
        print(f"\n>>>>>>>>>>>> [Turn {turn_count} 开始] <<<<<<<<<<<<")

        # 每次只传入当前轮的增量用户消息，历史记录由 checkpointer 自动关联
        inputs = {"messages": [HumanMessage(content=user_input)]}

        step = 0
        async for chunk in agent.astream(
            inputs,
            config=config,
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            step += 1
            chunk_type = chunk["type"]
            data = chunk["data"]

            print(f"\n--- [Turn {turn_count} | Step {step}] chunk['type'] = '{chunk_type}' ---")

            # 1. messages 模式探针
            if chunk_type == "messages":
                msg_chunk, metadata = data
                node = metadata.get("langgraph_node", "unknown")

                # 检查思考链 (DeepSeek 特有)
                reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
                # 检查正文增量
                content = msg_chunk.content
                # 检查工具调用参数碎片
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

        print(f"\n>>>>>>>>>>>> [Turn {turn_count} 结束] <<<<<<<<<<<<")


if __name__ == "__main__":
    asyncio.run(main())