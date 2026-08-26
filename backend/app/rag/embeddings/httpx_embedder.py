import asyncio

import httpx
from httpx import AsyncClient
from app.rag.embeddings.base import BaseEmbedder


class HttpxEmbedder(BaseEmbedder):
    """
       通过 HTTP Embedding 服务获取向量。

       自己管理 httpx.AsyncClient 的生命周期。
       """
    def __init__(
            self,
            base_url: str,
            model_name: str,
            embedding_api_key: str,
            max_connections: int = 100,
            max_keepalive_connections: int = 20,
            connect_timeout: float = 5.0,
            read_timeout: float = 30.0,
            write_timeout: float = 10.0,
            pool_timeout: float = 5.0
    ):
        self.base_url = base_url
        self.model_name = model_name
        self.embedding_api_key = embedding_api_key
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self.pool_timeout = pool_timeout
        self._client: AsyncClient | None = None

    async def startup(self) -> None:
        """
        创建http连接池
        :return:
        """
        if self._client is not None:
            return
        limits = httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
            keepalive_expiry=30.0
        )
        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.write_timeout,
            pool=self.pool_timeout
        )
        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout
        )
    async def shutdown(self) -> None:
        """
        关闭http连接池
        :return:
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "HttpxEmbedder has not been started. "
                "Call startup() before using it."
            )
        return self._client


    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本向量"""
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}"
        }
        payload = {
            "input": texts,
            "model": self.model_name
        }
        response = await self.client.post(
            url=self.base_url,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [
            item["embedding"]
            for item in data
        ]

    async def embed_query(self, text: str) -> list[float]:
        """获取检索Query向量"""
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}"
        }
        payload = {
            "input": text,
            "model": self.model_name
        }
        response = await self.client.post(
            url=self.base_url,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()["data"]
        return data[0]["embedding"]


async def test():
    from app.core.config import settings
    embedder = HttpxEmbedder(
        base_url = settings.embedding_base_url,
        model_name = settings.embedding_model_name,
        embedding_api_key = settings.embedding_api_key
    )
    await embedder.startup()
    embeddings = await embedder.embed_documents(["你好","hello"])
    print(len(embeddings[0])==settings.embedding_dimensions)
    print(len(embeddings[1]))
    await embedder.shutdown()

async def test_query():
    from app.core.config import settings
    embedder = HttpxEmbedder(
        base_url=settings.embedding_base_url,
        model_name=settings.embedding_model_name,
        embedding_api_key=settings.embedding_api_key
    )
    await embedder.startup()
    embedding = await embedder.embed_query("你好")
    print(type(embedding))
    print(len(embedding))
    await embedder.shutdown()

if __name__ == "__main__":
    asyncio.run(test_query())

