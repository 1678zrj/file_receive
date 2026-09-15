import asyncio

from app.core.rag_deps import get_rag_container
from app.rag.container import RAGContainer
from fastapi import Depends


class RAGSearchService:
    def __init__(
            self,
            rag_container: RAGContainer,
    ):
        self.embedder = rag_container.embedder
        self.vector_store = rag_container.vector_store


    async def search(self, query: str, scope: str, scope_id: str):
        filter = f'scope_id == "{scope_id}"'
        query_vector = await self.embedder.embed_query(query)
        return await self.vector_store.search(
            query,
            query_vector,
            filter
        )


async def get_rag_search_service(rag_container: RAGContainer = Depends(get_rag_container)):
    return RAGSearchService(rag_container)




if __name__ == "__main__":
    async def test():
        rag_container = RAGContainer()
        await rag_container.startup()
        rag_ser = RAGSearchService(rag_container)
        res = await rag_ser.search("jupyter内核", scope="course", scope_id="course_1")
        print(res)
        await rag_container.shutdown()
    asyncio.run(test())