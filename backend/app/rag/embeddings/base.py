from abc import abstractmethod
from app.rag.base import LifecycleComponent


class BaseEmbedder(LifecycleComponent):

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本向量"""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """获取检索Query向量"""
        pass
