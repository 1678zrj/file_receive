import asyncio

from pymilvus import AsyncMilvusClient, DataType, Function
from pymilvus.client.types import LoadState, FunctionType
from pymilvus import AnnSearchRequest
from app.rag.vector_stores.base import BaseVectorStore


class MilvusVectorStore(BaseVectorStore):

    def __init__(
            self,
            uri: str,
            token: str,
            collection_name: str,
    ):
        self.uri = uri
        self.token = token
        self.collection_name = collection_name
        self._client: AsyncMilvusClient | None = None

    async def startup(self):
        if self._client is not None:
            return
        self._client = AsyncMilvusClient(
            uri=self.uri,
            token=self.token
        )
        has_collection = await self._client.has_collection(collection_name=self.collection_name)
        if not has_collection:
            await self._create_collection()
        # load_collection函数是幂等的，重复操作（在collection已经load的情况下）也没事
        await self._client.load_collection(collection_name=self.collection_name)
        # 准确校验加载状态
        load_state_res = await self._client.get_load_state(collection_name=self.collection_name)
        state = load_state_res.get("state") if isinstance(load_state_res, dict) else load_state_res

        if state != LoadState.Loaded:
            print("Failed to load Milvus collection: %s, state: %s", self.collection_name, state)
            raise RuntimeError(f"Failed to load collection {self.collection_name}, state: {state}")

        print(f"Milvus collection '{self.collection_name}' loaded successfully")

    async def shutdown(self):
        # 关闭 Milvus Client
        # 注意这里不能释放collection，否则多worker情况下会影响其它worker
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def _create_collection(self):
        client = self.client
        schema = client.create_schema(
            auto_id=False,
            enable_dynamic_field=True
        )
        # 该id要自己生成
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=256)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
        analyzer_params = {
            "tokenizer": "standard",
            "filter": ["lowercase"]
        }
        schema.add_field("chunk_text", DataType.VARCHAR, max_length=16384, enable_analyzer=True, analyzer_params = analyzer_params, enable_match = True)
        # 添加file_record_id，用于快速查找文档对应的chunk
        schema.add_field("file_record_id", DataType.VARCHAR, max_length=256)
        schema.add_field("file_hash", DataType.VARCHAR, max_length=256)
        # 添加scope，如course, user
        schema.add_field("scope", DataType.VARCHAR, max_length=256)
        # 添加scope_id，用于进行各种过滤
        schema.add_field("scope_id", DataType.VARCHAR, max_length=256)
        # Add function to schema
        bm25_function = Function(
            name="text_bm25_emb",
            input_field_names=["chunk_text"],
            output_field_names=["sparse_vector"],
            function_type=FunctionType.BM25,
        )
        schema.add_function(bm25_function)
        # 为字段创建索引
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="dense_vector", index_type="AUTOINDEX", metric_type="IP")
        index_params.add_index(field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25",params={"inverted_index_algo": "DAAT_MAXSCORE"})
        index_params.add_index(field_name="chunk_text", index_type="AUTOINDEX")
        # 标量字段建立倒排索引（加速 scope 过滤与按文档删除）
        index_params.add_index(field_name="scope_id", index_name="idx_scope_id", index_type="INVERTED")
        index_params.add_index(field_name="file_record_id", index_name="idx_file_record_id", index_type="INVERTED")
        index_params.add_index(field_name="file_hash", index_name="idx_file_hash", index_type="INVERTED")
        index_params.add_index(field_name="scope", index_name="idx_scope", index_type="INVERTED")
        await client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params
        )
        if (await client.has_collection(self.collection_name)):
            print("Collection created successfully")
        else:
            print("Failed to create collection")

    @property
    def client(self) -> AsyncMilvusClient:
        if self._client is None:
            raise RuntimeError(
                "MilvusVectorStore has not been started. Call startup() before using it."
            )
        return self._client

    async def upsert(
            self,
            dense_vectors: list[list[float]],
            chunk_texts: list[str],
            file_record_id: str,
            file_hash: str,
            scope: str,
            scope_id: str
    ) -> dict:
        data = [
            {
                "id": f"{file_hash}_{scope_id}_{str(i)}",
                "dense_vector": dense_vector,
                "chunk_text": chunk_texts[i],
                "file_record_id": file_record_id,
                "file_hash": file_hash,
                "scope": scope,
                "scope_id": scope_id
            }
            for i, dense_vector in enumerate(dense_vectors)
        ]
        res = await self.client.upsert(
            collection_name=self.collection_name,
            data=data
        )
        return res





    async def search(
            self,
            query: str,
            query_vector: list[float],
            filters: str | None = None,
            limit: int = 10,
            output_fields: list[str] | None = None
    ):
        if output_fields is None:
            output_fields = [
                "chunk_text",
                "file_record_id",
                "file_hash",
                "scope",
                "scope_id"
            ]

        search_param_1 = {
            "data": [query_vector],
            "anns_field": "dense_vector",
            "param": {"nprobe": 10},
            "limit": limit * 2,
            "expr": filters
        }
        request_1 = AnnSearchRequest(**search_param_1)
        search_param_2 = {
            "data": [query],
            "anns_field": "sparse_vector",
            "limit": limit * 2,
            "expr": filters
        }
        request_2 = AnnSearchRequest(**search_param_2)
        reqs = [request_1, request_2]
        ranker = Function(
            name="rrf",
            input_field_names=[],
            function_type=FunctionType.RERANK,
            params={
                "reranker": "rrf",
                "k": 100
            }
        )
        res = await self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=reqs,
            ranker=ranker,
            limit=limit,
            output_fields=output_fields
        )


        pass



if __name__ == "__main__":
    async def main():
        vector_store = MilvusVectorStore(
            uri="http://localhost:19530",
            token="root:Milvus",
            collection_name="rag_documents"
        )
        await vector_store.startup()
        await vector_store.shutdown()
    asyncio.run(main())
    print(len("ba885cec75b6368705d563ce370e67d3e73d83712bf89ee44ae5140346ae7f99"))