import asyncio
import httpx
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from app.core.config import settings
from langchain_core.messages import HumanMessage
from httpx import AsyncClient
from enum import Enum


class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    CUSTOM = "custom"





"""
    进行连接池优化
    ChatDeepSeek不需要全局单例，
    真正需要全局单例的是底层维护的TCP连接池，因为ChatDeepSeek初始化的主要开销其实在TCP连接池上
    这样一来每次ChatDeepSeek初始化，都可以复用全局维护的TCP连接池，开销可以忽略不记
    就可以针对多用户的情况使用用户自己的model_name, api_key, base_url了，
    实现用户配置和TCP连接的解耦
"""
class LLMClientManager:
    def __init__(self):
        self._async_client: AsyncClient | None = None
        self._default_model_name = settings.model_name
        self._default_base_url = settings.base_url
        self._default_api_key = settings.api_key

    async def startup(self):
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = AsyncClient(
                limits=httpx.Limits(
                    max_keepalive_connections=50,  # 允许报错的长连接数
                    max_connections=200,  # 最大并发连接数
                    keepalive_expiry=30.0  # 连接空闲超时时长
                ),
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=120.0,
                    write=10.0,
                    pool=30.0
                )
            )

    async def shutdown(self):
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()

    def get_model(
            self,
            provider: str | None = None,
            api_key: str | None = None,
            base_url: str | None = None,
            model_name: str | None = None
    ) -> BaseChatModel:
        """
            轻量级工厂方法：
            传入用户自定义参数；若用户未提供，则回退到系统默认 settings。
            通过挂载全局 _async_client，完全省去新建 TCP/TLS 握手的开销。
        """
        if self._async_client is None or self._async_client.is_closed:
            raise RuntimeError("LLMClientManager has not been started. Call startup() first")
        if provider and api_key and base_url and model_name:
            if provider == LLMProvider.DEEPSEEK.value:
                return ChatDeepSeek(
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    http_async_client=self._async_client,
                    max_retries=0
                )
            elif provider == LLMProvider.OPENAI.value:
                return ChatOpenAI(
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    http_async_client=self._async_client,
                    max_retries=0
                )
            elif provider == LLMProvider.CUSTOM.value:
                return ChatOpenAI(
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    http_async_client=self._async_client,
                    max_retries=0
                )
            else:
                raise RuntimeError(f"Unsupported provider: {provider}")
        else:
            return ChatDeepSeek(
                model_name=self._default_model_name,
                api_key=self._default_api_key,
                base_url=self._default_base_url,
                http_async_client=self._async_client, # 核心：挂在全局连接池
                max_retries=0
            )


# model_container = ModelContainer(settings.base_url, settings.model_name, settings.api_key)
llm_client_manager = LLMClientManager()



async def main():

    # 模拟应用启动
    await llm_client_manager.startup()

    try:
        # 场景 A: 走系统默认配置
        default_model = llm_client_manager.get_model()
        try:
            res1 = await default_model.ainvoke([HumanMessage(content="你好")])
        except Exception as e:
            print(e.code)
            print(e.status_code)
            print(e.message)
            raise
        print("默认配置响应:", res1.content)

        # 场景 B: 走用户自定义的配置（多租户调用）
        # 即使这里传入了第三方代理 URL 或专属 Key，底层连接池也会自动按 Host 分流并复用
        user_model = llm_client_manager.get_model(
            provider="deepseek",
            api_key=settings.api_key,
            base_url=settings.base_url,
            model_name=settings.model_name
        )
        res2 = await user_model.ainvoke([HumanMessage(content="你好")])
        print("自定义配置响应:", res2)

    finally:
        # 模拟应用关闭
        await llm_client_manager.shutdown()



if __name__ == "__main__":
    asyncio.run(main())
