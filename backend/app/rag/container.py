import asyncio
from typing import Type

from app.rag.embeddings.base import BaseEmbedder
from app.rag.embeddings.httpx_embedder import HttpxEmbedder
from app.rag.vector_stores.base import BaseVectorStore
from app.rag.vector_stores.milvus_store import MilvusVectorStore
from app.rag.parsers.base import BaseParser
from app.rag.parsers.docx_parser import DocxParser
from app.rag.parsers.markdown_parser import MarkdownParser
from app.rag.splitters.base import BaseSplitter
from app.rag.splitters.recursive_splitter import RecursiveSplitter
from app.rag.splitters.markdown_spliter import MarkdownSplitter
from app.core.config import settings


class RAGContainer:

    def __init__(self):
        """
        RAG 组件组合根。

        职责：

        1. 根据配置选择具体实现
        2. 创建 RAG 组件
        3. 统一启动组件
        4. 统一关闭组件
        5. 对外暴露抽象接口
        """
        # 有状态组件，需生命周期管理
        self._embedder: BaseEmbedder | None = None
        self._vector_store: BaseVectorStore | None = None
        self._started = False
        # 无状态组件
        self._parser_registry: dict[str, Type[BaseParser]] = {}
        self._splitter_registry: dict[str, Type[BaseSplitter]] = {}
        # 注册解析，分块
        self._register_default_parsers()
        self._register_default_splitters()

    def _register_default_parsers(self):
        self._parser_registry[".docx"] = DocxParser
        self._parser_registry[".md"] = MarkdownParser
        self._parser_registry["md"] = MarkdownParser


    def get_parser(self, file_extension: str) -> BaseParser:
        """根据文件后缀获取对应的解析器"""
        ext = file_extension.lower()
        parser_cls = self._parser_registry.get(ext)
        if parser_cls is None:
            raise ValueError(f"No parser registered for file extension: {ext}")
        return parser_cls()

    def _register_default_splitters(self):
        self._splitter_registry["recursive"] = RecursiveSplitter
        self._splitter_registry["markdown"] = MarkdownSplitter

    def get_splitter(self, splitter_type: str | None = None, **kwargs) -> BaseSplitter:
        s_type = splitter_type if splitter_type else settings.rag_splitter_type
        splitter_cls = self._splitter_registry.get(s_type)
        if splitter_cls is None:
            raise ValueError(f"Unsupported splitter strategy: {s_type}")

        return splitter_cls(**kwargs)

    def _build_embedder(self) -> BaseEmbedder:
        embedder_type = settings.rag_embedder_type
        if embedder_type == "httpx":
            return HttpxEmbedder(
                base_url=settings.embedding_base_url,
                model_name=settings.embedding_model_name,
                embedding_api_key=settings.embedding_api_key
            )

        raise ValueError(
            f"Unknown embedder type: {embedder_type}"
        )

    def _build_vector_store(self) -> BaseVectorStore:
        vector_store_type = settings.rag_vector_store_type
        if vector_store_type == "milvus":
            return MilvusVectorStore(
                uri=settings.milvus_uri,
                token=settings.milvus_token,
                collection_name=settings.milvus_collection_name
            )
        raise ValueError(
            f"Unknown vector store type: {vector_store_type}"
        )

    # 生命周期管理
    async def startup(self) -> None:
        if self._started:
            return
        embedder = self._build_embedder()
        vector_store = self._build_vector_store()
        try:
            await embedder.startup()
            await vector_store.startup()
        except Exception:
            try:
                await vector_store.shutdown()
            finally:
                await embedder.shutdown()
            raise
        self._embedder = embedder
        self._vector_store = vector_store
        self._started = True

    async def shutdown(self):
        if not self._started:
            return
        if self._embedder is not None:
            await self._embedder.shutdown()
        if self._vector_store is not None:
            await self._vector_store.shutdown()
        self._embedder = None
        self._vector_store = None
        self._started = False

    @property
    def embedder(self) -> BaseEmbedder:
        if self._embedder is None:
            raise RuntimeError(
                "RAGContainer has not been started."
            )
        return self._embedder

    @property
    def vector_store(self) -> BaseVectorStore:
        if self._vector_store is None:
            raise RuntimeError(
                "RAGContainer has not been started."
            )
        return self._vector_store
async def main():
    rag_container = RAGContainer()
    await rag_container.startup()
    await rag_container.shutdown()
if __name__ == "__main__":
    asyncio.run(main())