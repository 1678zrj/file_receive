import asyncio
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from app.rag_agent.state import OverAllState
from app.rag_agent.model import llm_client_manager
from app.rag_agent.tool_registry import tool_registry
from app.rag_agent.llm_exception import normalize_llm_exception, LLMUnknownError
from langchain_core.messages import AIMessage, BaseMessage
import random


logger = logging.Logger(__name__)
# 指数退避算法核心参数
# 初次延迟时间
# 每次延迟时间是上一次延迟时间的多少倍
# 当前是第几次重试
def calculate_wait_time(
        attempt: int, #第几次重试
        initial_delay: float = 1.0, # 初次延迟时间
        backoff_factor: float = 2.0, # 当前延迟时间是上一次延迟时间的多少倍
        max_delay: float = 30.0 # 最大等待时间
) -> float:
    """计算指数退避等待时间 (Full Jitter)，带上限保护"""
    calculated_wait = initial_delay * (backoff_factor ** attempt)
    # 限制等待上限，防止极端情况下延迟过大
    capped_wait = min(calculated_wait, max_delay)
    # Full Jitter 抖动，打散并发请求
    return random.uniform(0, capped_wait)

async def run_model_with_retry(
        messages: list[BaseMessage],
        model_with_tools: BaseChatModel,
        config: RunnableConfig,
        max_retries: int = 3,

) -> AIMessage:
    # 这里加1是因为第一次不算重试
    for i in range(max_retries + 1):
        try:
            response = await model_with_tools.ainvoke(messages, config)
            return response
        except Exception as e:
            # 转换得到的异常，根据异常的is_retry_able属性，采取重试策略
            trans_exc = normalize_llm_exception(e)
            # 不可重试的异常
            if not trans_exc.is_retryable:
                logger.error(
                    f"LLM call encountered non-retryable exception: {trans_exc.message}"
                )
                raise trans_exc from e
            # 可以重试的异常，使用指数退避算法
            # 但在这之前要判断这是第几次重试了，如果已经是最后一次，那么直接抛出异常
            if i == max_retries:
                logger.error(
                    f"LLM call reached max retries ({max_retries}). Giving up."
                )
                raise trans_exc from e
            # 到这里开始指数退避重试，先计算等待时间
            wait_time = calculate_wait_time(
                attempt=i
            )
            logger.warning(
                f"LLM call failed (attempt {i + 1}/{max_retries + 1}): {trans_exc.message}. "
                f"Retrying in {wait_time:.2f}s..."
            )
            await asyncio.sleep(wait_time)

    # 兜底，理论上不会走到这里
    raise LLMUnknownError(message="Model invocation failed with unknown exception.")



async def call_model(state: OverAllState, config: RunnableConfig):
    # 获取当前的消息列表
    messages = state["messages"]
    # 动态从 config 中获取当前用户的个性化配置（若无则取 None，走系统默认）
    configurable = config.get("configurable", {})
    user_provider = configurable.get("provider")
    user_api_key = configurable.get("api_key")
    user_base_url = configurable.get("base_url")
    user_model_name = configurable.get("model_name")
    user_role = configurable.get("user_role")
    tools = tool_registry.get_role_tools(user_role)
    model = llm_client_manager.get_model(
        provider=user_provider,
        api_key=user_api_key,
        base_url=user_base_url,
        model_name=user_model_name
    )
    model_with_tools = model.bind_tools(tools)
    response = await run_model_with_retry(messages, model_with_tools, config)
    return {"messages": [response]}
