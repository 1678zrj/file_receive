import asyncio
import sys

from langgraph.graph.state import CompiledStateGraph
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.rag_agent.graph import graph_builder
from app.core.config import settings


class GraphContainer:
    def __init__(self, psycopg_url: str):
        self.psycopg_url = psycopg_url
        self._graph: CompiledStateGraph | None = None
        self._pool: AsyncConnectionPool | None = None


    async def startup(self):

        if self._pool is None:
            # 1. 设置 open=False，阻止在构造函数中自动打开
            self._pool = AsyncConnectionPool(
                conninfo=self.psycopg_url,
                max_size=8,
                kwargs={"autocommit": True},
                open=False
            )
            await self._pool.open()
        if self._graph is None:
            checkpointer = AsyncPostgresSaver(self._pool)
            await checkpointer.setup()
            self._graph = graph_builder.compile(checkpointer=checkpointer)

    async def shutdown(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._graph = None

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("")
        return self._graph


graph_container = GraphContainer(psycopg_url=settings.psycopg_url)
