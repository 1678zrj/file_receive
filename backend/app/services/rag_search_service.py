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


    async def search_course_kb(self):

        pass


async def get_rag_search_service(rag_container: RAGContainer = Depends(get_rag_container)):
    return RAGSearchService(rag_container)
