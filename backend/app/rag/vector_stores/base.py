from abc import abstractmethod

from app.rag.base import LifecycleComponent




class BaseVectorStore(LifecycleComponent):
    """
    Vector Store 抽象接口
    """

    @abstractmethod
    async def upsert(
            self,
            dense_vectors: list[list[float]],
            chunk_texts: list[str],
            file_record_id: str,
            file_hash: str,
            scope: str,
            scope_id: str
    ) -> bool:
        raise NotImplementedError


    @abstractmethod
    async def search(
            self,
            query: str,
            query_vector: list[float],
            filter: str,
            limit: int = 10
    ):
        raise NotImplementedError
