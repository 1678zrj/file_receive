from abc import abstractmethod

from app.rag.base import LifecycleComponent




class BaseVectorStore(LifecycleComponent):
    """
    Vector Store 抽象接口
    """

    @abstractmethod
    async def insert(
            self,
            dense_vectors: list[list[float]],
            chunk_texts: list[str],
            knowledge_doc_id: int,
            file_record_id: int,
            file_hash: str,
            scope: str,
            scope_id: str,
            is_enabled: bool = True
    ) -> dict:
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

    @abstractmethod
    async def delete_by_doc_id(
            self,
            knowledge_doc_id: int
    ):
        raise NotImplementedError
    @abstractmethod
    async def delete_by_doc_ids(
            self,
            knowledge_doc_ids: list[int]
    ):
        raise NotImplementedError
