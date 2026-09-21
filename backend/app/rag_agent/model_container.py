import asyncio

from langchain_deepseek import ChatDeepSeek
from app.core.config import settings
from langchain_core.messages import HumanMessage



class ModelContainer:
    def __init__(
            self,
            base_url: str,
            model_name: str,
            api_key: str
    ):
        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key
        self._model: ChatDeepSeek | None = None

    async def startup(self) -> None:
        if self._model is None:
            self._model = ChatDeepSeek(
                model_name=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url
            )

    @property
    def model(self) -> ChatDeepSeek:
        if self._model is None:
            raise RuntimeError(f"LLM Model has not been initialized")
        return self._model


model_container = ModelContainer(settings.base_url, settings.model_name, settings.api_key)

async def main():
    await model_container.startup()
    model = model_container.model
    response = await model.ainvoke([HumanMessage(content="你好")])
    print(response)

if __name__ == "__main__":
    asyncio.run(main())