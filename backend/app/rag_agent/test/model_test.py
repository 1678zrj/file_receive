from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.core.config import settings
import asyncio
from langchain_deepseek import ChatDeepSeek




async def main():
    model = ChatDeepSeek(
        base_url=settings.base_url,
        model=settings.model_name,
        api_key=settings.api_key
    )
    response: AIMessage = await model.ainvoke([HumanMessage(content="hello")])
    print(response)
    print(response.additional_kwargs.get("reasoning_content"))
    print(response.content)
    print(response.response_metadata)


if __name__ == "__main__":
    asyncio.run(main())

