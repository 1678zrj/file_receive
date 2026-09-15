# import asyncio
# import json
# from langchain_core.messages import HumanMessage, ToolMessage
# from langchain_core.tools import tool
# from langchain_deepseek import ChatDeepSeek
# from app.core.config import settings
#
#
# @tool
# def get_weather(location: str) -> str:
#     """获取指定城市的实时天气预报信息。
#
#     Args:
#         location: 目标城市或地区名称，例如 '北京'、'上海'、'广州'
#     """
#     mock_db = {
#         "北京": {"condition": "晴朗", "temperature": "23°C", "humidity": "42%", "wind": "微风"},
#         "上海": {"condition": "多云转阴", "temperature": "25°C", "humidity": "68%", "wind": "东南风 3级"},
#         "广州": {"condition": "雷阵雨", "temperature": "30°C", "humidity": "85%", "wind": "无风"},
#     }
#     info = mock_db.get(
#         location,
#         {"condition": "晴", "temperature": "24°C", "humidity": "50%", "wind": "微风"},
#     )
#     return json.dumps(info, ensure_ascii=False)
#
#
# async def main():
#     model = ChatDeepSeek(
#         base_url=settings.base_url,
#         model=settings.model_name,
#         api_key=settings.api_key,
#     )
#     model_with_tools = model.bind_tools([get_weather])
#
#     # 全局对话历史，维持多轮记忆
#     messages = []
#
#     print("=== 多轮对话已启动（输入 exit 或 quit 退出）===")
#
#     # 外层循环：多轮人机交互
#     while True:
#         user_input = await asyncio.to_thread(input, "\nUser: ")
#         user_input = user_input.strip()
#
#         if not user_input:
#             continue
#         if user_input.lower() in ["exit", "quit", "q"]:
#             print("对话结束。")
#             break
#
#         messages.append(HumanMessage(content=user_input))
#
#         # 内层循环：处理单轮任务中的思维链与工具调用链
#         while True:
#             from langchain_core.messages import AIMessage, AIMessageChunk
#
#             # 1. 初始化收集容器
#             full_chunk: AIMessageChunk | None = None
#             full_reasoning = ""
#
#             async for chunk in model_with_tools.astream(messages, stream_usage=True):
#                 # a. 累加基础 chunk
#                 if full_chunk is None:
#                     full_chunk = chunk
#                 else:
#                     full_chunk += chunk
#
#                 # b. 显式流式消费 reasoning
#                 r_chunk = chunk.additional_kwargs.get("reasoning_content", "")
#                 if r_chunk:
#                     print(r_chunk, end="", flush=True)
#                     full_reasoning += r_chunk
#
#                 # c. 显式流式消费正文
#                 if chunk.content:
#                     print(chunk.content, end="", flush=True)
#
#             # 2. 固化为标准的 AIMessage（清理流式临时字段，合并元数据）
#             full_response = AIMessage(
#                 content=full_chunk.content,
#                 tool_calls=full_chunk.tool_calls,  # 由 chunk 加法自动聚合好的结构化参数
#                 invalid_tool_calls=full_chunk.invalid_tool_calls,
#                 additional_kwargs={
#                     **full_chunk.additional_kwargs,
#                     "reasoning_content": full_reasoning,  # 确保完整思考链不丢失
#                 },
#                 response_metadata=full_chunk.response_metadata,  # 保留 finish_reason、system_fingerprint 等
#                 usage_metadata=full_chunk.usage_metadata,  # 明确保留 token 和缓存统计
#                 id=full_chunk.id,
#             )
#
#             # 3. 将标准无污染的 AIMessage 推入历史记录
#             messages.append(full_response)
#
#             print(full_response)
#
#             # 无工具调用需求，说明回答已完结，退出内层循环等待下一轮用户输入
#             if not full_response.tool_calls:
#                 break
#
#             # 处理并执行工具调用
#             for tool_call in full_response.tool_calls:
#                 print(f"[调用工具] {tool_call['name']}({tool_call['args']})")
#                 if tool_call["name"] == "get_weather":
#                     tool_output = await get_weather.ainvoke(tool_call["args"])
#                     messages.append(
#                         ToolMessage(
#                             content=tool_output,
#                             tool_call_id=tool_call["id"],
#                         )
#                     )
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
import asyncio
import json
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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
    messages = []

    print("=== 多轮对话已启动（输入 exit 或 quit 退出）===")

    while True:
        user_input = await asyncio.to_thread(input, "\nUser: ")
        user_input = user_input.strip()

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("对话结束。")
            break

        messages.append(HumanMessage(content=user_input))

        # Agent 内部执行流（可能包含多次推理/工具调用）
        while True:
            full_chunk = None
            full_reasoning = ""
            in_reasoning = False
            in_content = False

            # 流式传输并保留 usage
            async for chunk in model_with_tools.astream(messages, stream_usage=True):
                if full_chunk is None:
                    full_chunk = chunk
                else:
                    full_chunk += chunk

                # 1. 打印思考链
                reasoning_chunk = chunk.additional_kwargs.get("reasoning_content", "")
                if reasoning_chunk:
                    if not in_reasoning:
                        print("\n[思考过程] ", end="", flush=True)
                        in_reasoning = True
                    print(reasoning_chunk, end="", flush=True)
                    full_reasoning += reasoning_chunk

                # 2. 打印回答正文
                if chunk.content:
                    if not in_content:
                        prefix = "\n\n[回答] " if in_reasoning else "\n[回答] "
                        print(prefix, end="", flush=True)
                        in_content = True
                    print(chunk.content, end="", flush=True)

            print()  # 确保流结束后换行

            # 3. 将 AIMessageChunk 升格为标准无污染的 AIMessage
            full_response = AIMessage(
                content=full_chunk.content,
                tool_calls=full_chunk.tool_calls,
                invalid_tool_calls=full_chunk.invalid_tool_calls,
                additional_kwargs={
                    **full_chunk.additional_kwargs,
                    "reasoning_content": full_reasoning,
                },
                response_metadata=full_chunk.response_metadata,
                usage_metadata=full_chunk.usage_metadata,
                id=full_chunk.id,
            )

            # 调试信息单独换行打印，避免污染正文
            # print(f"\n[Debug Metadata]: tokens={full_response.usage_metadata}")

            messages.append(full_response)

            # 无工具调用需求，说明回答完毕，回到外层循环等待用户
            if not full_response.tool_calls:
                break

            # 4. 执行工具调用
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