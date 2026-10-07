from fastapi import Depends, Request
from app.rag.container import RAGContainer
from app.rag.vector_stores.base import BaseVectorStore
from app.rag.embeddings.base import BaseEmbedder

rag_container = RAGContainer()

def get_rag_container_sync() -> RAGContainer:
    return rag_container

async def get_rag_container() -> RAGContainer:
    return rag_container


async def get_embedder() -> BaseEmbedder:
    return rag_container.embedder


async def get_vector_store() -> BaseVectorStore:
    return rag_container.vector_store
