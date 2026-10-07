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
        location: 目标城市或地区名称，例如 '北京'、'上海'
    """
    mock_db = {
        "北京": {"condition": "晴朗", "temperature": "23°C", "humidity": "42%", "wind": "微风"},
        "上海": {"condition": "多云转阴", "temperature": "25°C", "humidity": "68%", "wind": "东南风 3级"},
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

    messages = [HumanMessage(content="今天北京天气如何？")]

    while True:
        full_response = None
        full_reasoning = ""
        in_reasoning = False
        in_content = False

        # 1. 流式调用模型
        async for chunk in model_with_tools.astream(messages):
            # 累加消息分块以保持完整的 tool_calls 与 metadata
            if full_response is None:
                full_response = chunk
            else:
                full_response += chunk

            # 2. 提取流式思考内容 (DeepSeek 特有字段)
            reasoning_chunk = chunk.additional_kwargs.get("reasoning_content", "")
            if reasoning_chunk:
                if not in_reasoning:
                    print("\n[思考过程]：", end="", flush=True)
                    in_reasoning = True
                print(reasoning_chunk, end="", flush=True)
                full_reasoning += reasoning_chunk

            # 3. 提取流式正文内容
            if chunk.content:
                if not in_content:
                    if in_reasoning:
                        print("\n\n[回答]：", end="", flush=True)
                    in_content = True
                print(chunk.content, end="", flush=True)

        print()  # 换行

        # 4. 显式补全思考内容，避免下轮请求因缺失 reasoning 报错
        if full_reasoning:
            full_response.additional_kwargs["reasoning_content"] = full_reasoning

        messages.append(full_response)

        # 5. 没有工具调用，说明本次交互闭环，退出循环
        if not full_response.tool_calls:
            break

        # 6. 处理并执行工具调用
        for tool_call in full_response.tool_calls:
            print(f"\n[执行工具]：{tool_call['name']} 参数：{tool_call['args']}")
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