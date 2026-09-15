import json
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """获取指定城市的实时天气预报信息。

    Args:
        location: 目标城市或地区名称，例如 '北京'、'上海'
    """
    # 模拟的天气数据字典
    mock_db = {
        "北京": {"condition": "晴朗", "temperature": "23°C", "humidity": "42%", "wind": "微风"},
        "上海": {"condition": "多云转阴", "temperature": "25°C", "humidity": "68%", "wind": "东南风 3级"},
        "广州": {"condition": "雷阵雨", "temperature": "30°C", "humidity": "85%", "wind": "无风"},
        "深圳": {"condition": "阵雨", "temperature": "29°C", "humidity": "78%", "wind": "微风"},
    }

    # 查表或返回默认模拟数据
    info = mock_db.get(
        location,
        {"condition": "晴", "temperature": "24°C", "humidity": "50%", "wind": "微风"}
    )
    return json.dumps(info, ensure_ascii=False)

import asyncio
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_deepseek import ChatDeepSeek
from app.core.config import settings

# 引入上面定义的 get_weather 工具
# from your_module import get_weather

async def main():
    model = ChatDeepSeek(
        base_url=settings.base_url,
        model=settings.model_name,
        api_key=settings.api_key,
    )

    # 1. 注册工具到模型
    model_with_tools = model.bind_tools([get_weather])

    messages = [HumanMessage(content="今天北京天气如何？")]

    # 2. 第一轮请求：模型分析后返回 tool_calls
    ai_msg = await model_with_tools.ainvoke(messages)
    print(ai_msg)
    messages.append(ai_msg)

    # 3. 处理工具调用
    if ai_msg.tool_calls:
        for tool_call in ai_msg.tool_calls:
            if tool_call["name"] == "get_weather":
                # 直接使用 args 调用异步工具
                tool_output = await get_weather.ainvoke(tool_call["args"])

                # 构造 ToolMessage 追加到上下文中
                messages.append(
                    ToolMessage(
                        content=tool_output,
                        tool_call_id=tool_call["id"],
                    )
                )

        # 4. 第二轮请求：模型根据工具返回的数据生成最终自然语言回复
        final_response = await model_with_tools.ainvoke(messages)
        print(final_response)
        print("最终结果：", final_response.content)


if __name__ == "__main__":
    asyncio.run(main())