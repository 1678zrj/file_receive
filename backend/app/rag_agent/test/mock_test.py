import asyncio
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from app.core.config import settings  # 替换为你自己的配置导入


# 1. 定义一个简单的测试工具并绑定
@tool
def get_current_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}的天气是晴天，22℃"


tools = [get_current_weather]
model = ChatDeepSeek(
    model_name=settings.model_name,
    api_key=settings.api_key,
    base_url=settings.base_url,
)
model_with_tools = model.bind_tools(tools)


# 2. 伪造公共上下文：第1步用户提问，第3步工具返回结果
tool_call_id = "call_mock_weather_001"

human_msg = HumanMessage(content="今天北京天气怎么样？")

tool_msg = ToolMessage(
    tool_call_id=tool_call_id,
    name="get_current_weather",
    content="北京今天晴天，气温 15°C ~ 25°C，微风。",
)


async def test_with_reasoning():
    print("\n========== 测试 1：包含 reasoning_content ==========")
    # 构造带有思考内容的 AIMessage
    mock_ai_with_reasoning = AIMessage(
        content="",
        additional_kwargs={
            # 关键字段：模拟上一轮模型产生的真实思考链
            "reasoning_content": "用户询问今天北京的天气情况。我需要使用 get_current_weather 工具来查询北京的天气数据。"
        },
        tool_calls=[
            {
                "name": "get_current_weather",
                "args": {"city": "北京"},
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )

    messages = [human_msg, mock_ai_with_reasoning, tool_msg]

    try:
        # 查看 LangChain 真正准备发给 OpenAI/DeepSeek 接口的数据
        payload, _ = model._create_message_dicts(messages, None)
        print("实际发送给 API 的 assistant 报文：", payload[1])
        response = await model_with_tools.ainvoke(messages)
        print("✅ 请求成功！DeepSeek 正常回复：")
        print(response.content)
    except Exception as e:
        print("❌ 请求失败：", e)


async def test_without_reasoning():
    print("\n========== 测试 2：缺少 reasoning_content ==========")
    # 构造缺失思考内容的 AIMessage（模拟从其他普通模型转移过来的历史消息）
    mock_ai_without_reasoning = AIMessage(
        content="",
        # 故意置空或不带 reasoning_content
        additional_kwargs={},
        tool_calls=[
            {
                "name": "get_current_weather",
                "args": {"city": "北京"},
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )

    messages = [human_msg, mock_ai_without_reasoning, tool_msg]

    try:
        response = await model_with_tools.ainvoke(messages)
        print("✅ 请求成功：", response.content)
    except Exception as e:
        print("❌ 复现官方 400 校验拦截：")
        print(e)


async def main():
    await test_with_reasoning()
    await test_without_reasoning()


if __name__ == "__main__":
    asyncio.run(main())