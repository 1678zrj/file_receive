import asyncio
import json
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from app.core.config import settings


@tool
def get_weather(location: str) -> str:
    """获取指定城市的实时天气预报信息。

    Args:
        location: 目标城市或地区名称，例如 '北京'、'上海'、'广州'
    """
    mock_db = {
        "北京": {"condition": "晴朗", "temperature": "23°C", "humidity": "42%", "wind": "微风"},
        "上海": {"condition": "多云转阴", "temperature": "25°C", "humidity": "68%", "wind": "东南风 3级"},
        "广州": {"condition": "雷阵雨", "temperature": "30°C", "humidity": "85%", "wind": "无风"},
    }
    info = mock_db.get(
        location,
        {"condition": "晴", "temperature": "24°C", "humidity": "50%", "wind": "微风"},
    )
    return json.dumps(info, ensure_ascii=False)


async def main():
    model = ChatDeepSeek(
        base_url=settings.base_url,
        model=settings.model_name,
        api_key=settings.api_key,
    )
    model_with_tools = model.bind_tools([get_weather])

    # 全局对话历史，维持多轮记忆
    messages = []

    print("=== 多轮对话已启动（输入 exit 或 quit 退出）===")

    # 外层循环：多轮人机交互
    while True:
        user_input = await asyncio.to_thread(input, "\nUser: ")
        user_input = user_input.strip()

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("对话结束。")
            break

        messages.append(HumanMessage(content=user_input))

        # 内层循环：处理单轮任务中的思维链与工具调用链
        while True:
            full_response = None
            full_reasoning = ""
            in_reasoning = False
            in_content = False

            # 流式获取模型输出
            async for chunk in model_with_tools.astream(messages):
                if full_response is None:
                    full_response = chunk
                else:
                    full_response += chunk

                # 流式输出思考链
                reasoning_chunk = chunk.additional_kwargs.get("reasoning_content", "")
                if reasoning_chunk:
                    if not in_reasoning:
                        print("\n[思考过程] ", end="", flush=True)
                        in_reasoning = True
                    print(reasoning_chunk, end="", flush=True)
                    full_reasoning += reasoning_chunk

                # 流式输出正文内容
                if chunk.content:
                    if not in_content:
                        if in_reasoning:
                            print("\n\n[回答] ", end="", flush=True)
                        else:
                            print("\n[回答] ", end="", flush=True)
                        in_content = True
                    print(chunk.content, end="", flush=True)

            print()

            # 关键：手动补齐思考字段，确保下轮调用不丢上下文校验
            if full_reasoning:
                full_response.additional_kwargs["reasoning_content"] = full_reasoning

            messages.append(full_response)
            print(full_response)

            # 无工具调用需求，说明回答已完结，退出内层循环等待下一轮用户输入
            if not full_response.tool_calls:
                break

            # 处理并执行工具调用
            for tool_call in full_response.tool_calls:
                print(f"[调用工具] {tool_call['name']}({tool_call['args']})")
                if tool_call["name"] == "get_weather":
                    tool_output = await get_weather.ainvoke(tool_call["args"])
                    messages.append(
                        ToolMessage(
                            content=tool_output,
                            tool_call_id=tool_call["id"],
                        )
                    )


if __name__ == "__main__":
    asyncio.run(main())