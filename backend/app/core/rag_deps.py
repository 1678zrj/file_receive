from fastapi import Depends, Request
from app.rag.container import RAGContainer
from app.rag.vector_stores.base import BaseVectorStore
from app.rag.embeddings.base import BaseEmbedder


async def get_rag(request: Request) -> RAGContainer:
    return request.app.state.rag


async def get_embedder(rag: RAGContainer = Depends(get_rag)) -> BaseEmbedder:
    return rag.embedder


async def get_vector_store(rag: RAGContainer = Depends(get_rag)) -> BaseVectorStore:
    return rag.vector_store
