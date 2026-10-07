import json
import time
from dataclasses import dataclass, field
from enum import Enum

from fastapi import Depends
from redis.asyncio import Redis
from app.redis.redis_client import get_redis


class UploadStatus(str, Enum):
    UPLOADING = "uploading"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class UploadSession:
    user_id: int
    upload_id: str
    file_name: str
    file_hash: str
    file_ext: str
    mime_type: str
    total_size: int
    chunk_size: int
    total_chunks: int
    status: UploadStatus = UploadStatus.UPLOADING
    file_record_id: int | None = None
    error_msg: str | None = None
    uploaded_chunks: set[int] = field(default_factory=set)
    updated_at: float = 0.0


class SessionManager:
    # Lua脚本: 原子判定任务, 活跃态或已完成态均滑动续期并直接返回
    INIT_SESSION_LUA = """
        local user_hash_key = KEYS[1]
        local new_upload_id = ARGV[1]
        local meta_prefix = ARGV[2]
        local chunks_prefix = ARGV[3]
        local meta_json = ARGV[4]
        local ttl = tonumber(ARGV[5])
        
        local existing_upload_id = redis.call('GET', user_hash_key)
        if existing_upload_id then
            local existing_meta_key = meta_prefix .. existing_upload_id
            local raw_meta = redis.call('GET', existing_meta_key)
            if raw_meta then
                local data = cjson.decode(raw_meta)
                -- 活跃态: 统一续期并返回已有会话
                -- completed作为应该终态被清理
                -- 否则会存在数据库记录没有却秒传的诡异情况,最终都得以数据库记录为准
                if data['status'] == 'uploading' or data['status'] == 'merging' then
                    redis.call('EXPIRE', user_hash_key, ttl)
                    redis.call('EXPIRE', existing_meta_key, ttl)
                    redis.call('EXPIRE', chunks_prefix .. existing_upload_id, ttl)
                    return {0, existing_upload_id, raw_meta}
                end
                -- 对于完成态或失败态的情况,清理历史残留
                redis.call('DEL', chunks_prefix .. existing_upload_id)
                redis.call('DEL', existing_meta_key)
            end
        end
        -- 任务不存在/过期/失败 : 原子创建新任务并初始化TTL
        local new_meta_key = meta_prefix .. new_upload_id
        redis.call('SET', user_hash_key, new_upload_id, 'EX', ttl)
        redis.call('SET', new_meta_key, meta_json, 'EX', ttl)
        return {1, new_upload_id, meta_json}
    """
    # 上传文本块分片时原子检测Meta存在性,记录分片并同一续期的Lua脚本
    ADD_CHUNK_LUA = """
        local meta_key = KEYS[1]
        local chunks_key = KEYS[2]
        local user_hash_key = KEYS[3]
        local chunk_index = tonumber(ARGV[1])
        local ttl = tonumber(ARGV[2])
        
        -- 检查会话是否存在
        if redis.call('EXISTS', meta_key) == 0 then
            return 0
        end
        -- 写入分片并统一续期
        redis.call('SADD', chunks_key, chunk_index)
        redis.call('EXPIRE', meta_key, ttl)
        redis.call('EXPIRE', chunks_key, ttl)
        redis.call('EXPIRE', user_hash_key, ttl)
    """
    # 原子CAS状态转换并全量刷新关联Key的TTL
    CAS_STATUS_LUA = """
        local meta_key = KEYS[1]
        local user_hash_key = KEYS[2]
        local chunks_key = KEYS[3]
        
        local expected_status = ARGV[1]
        local new_status = ARGV[2]
        local now_ts = ARGV[3]
        local ttl = ARGV[4]
        
        local raw_meta = redis.call('GET', meta_key)
        if not raw_meta then
            return -1
        end
        local data = cjson.decode(raw_meta)
        if data['status'] == expected_status then
            data['status'] = new_status
            data['updated_at'] = now_ts
            redis.call('SET', meta_key, cjson.encode(data), 'EX', ttl)
            redis.call('EXPIRE', user_hash_key, ttl)
            redis.call('EXPIRE', chunks_key, ttl)
            return 1
        end
        return 0
    """
    SET_FINAL_STATUS_LUA = """
        local meta_key = KEYS[1]
        local new_status = ARGV[1]
        local file_record_id = ARGV[2]
        local error_msg = ARGV[3]
        local now_ts = tonumber(ARGV[4])
        local ttl = tonumber(ARGV[5])
        
        local raw_meta = redis.call('GET', meta_key)
        if not raw_meta then
            return 0
        end
        local data = cjson.decode(raw_meta)
        if data['status'] == "completed" then
            return 1
        end
        data['status'] = new_status
        data['updated_at'] = now_ts
        if file_record_id ~= "" then
            data['file_record_id'] = tonumber(file_record_id)
        end
        if error_msg ~= "" then
            data['error_msg'] = error_msg
        end
        redis.call('SET', meta_key, cjson.encode(data), 'EX', ttl)
        return 1
    """


    def __init__(self, redis_client: Redis, ttl: int = 86400):
        self.redis = redis_client
        self.prefix = "upload"
        self.ttl = ttl

    def _meta_key(self, upload_id: str) -> str:
        return f"{self.prefix}:meta:{upload_id}"

    def _chunks_key(self, upload_id: str) -> str:
        return f"{self.prefix}:chunks:{upload_id}"

    def _user_hash_key(self, user_id: int, file_hash: str) -> str:
        return f"{self.prefix}:user_idx:{str(user_id)}:{file_hash}"

    async def get_upload_id_by_user_hash(self, user_id: int, file_hash: str) -> str | None:
        idx_key = self._user_hash_key(user_id, file_hash)
        upload_id = await self.redis.get(idx_key)
        return upload_id.decode() if upload_id else None

    async def get_or_create_session(
            self,
            user_id: int,
            upload_id_generator,
            file_data: dict
    ) -> tuple[UploadSession, bool]:
        """
            利用 Redis SETNX 消除 Init 阶段并发创建会话的Check-Then-Act,
            返回:(session, is_new_created)
        """
        user_hash_k = self._user_hash_key(user_id, file_data["file_hash"])
        new_upload_id = upload_id_generator()
        meta_payload = {
            "user_id": user_id,
            "upload_id": new_upload_id,
            "status": UploadStatus.UPLOADING.value,
            "updated_at": time.time(),
            **file_data
        }
        # 执行lua脚本,返回的结果有是否是新建的,upload_id,元数据
        result = await self.redis.eval(
            self.INIT_SESSION_LUA,
            1,
            user_hash_k,
            new_upload_id,
            "upload:meta:",
            "upload:chunks:",
            json.dumps(meta_payload),
            self.ttl
        )
        # 返回的结果中,0表示任务已存在,且未过期
        is_new_created = (result[0] == 1)
        actual_upload_id = result[1]
        raw_meta = result[2]
        meta_dict = json.loads(raw_meta)
        uploaded_chunks = set()
        if not is_new_created:
            chunks = await self.redis.smembers(self._chunks_key(actual_upload_id))
            uploaded_chunks = {int(chunk_index) for chunk_index in chunks}

        return UploadSession(
            **meta_dict,
            uploaded_chunks=uploaded_chunks
        ), is_new_created

    async def add_session(
            self,
            user_id: int,
            upload_id: str,
            file_name: str,
            file_hash: str,
            file_ext: str,
            mime_type: str,
            total_size: int,
            chunk_size: int,
            total_chunks: int
    ) -> UploadSession:
        meta_key = self._meta_key(upload_id)
        idx_key = self._user_hash_key(user_id, file_hash)
        mapping = {
            "upload_id": upload_id,
            "user_id": str(user_id),
            "file_name": file_name,
            "file_hash": file_hash,
            "file_ext": file_ext,
            "mime_type": mime_type,
            "total_size": str(total_size),
            "chunk_size": str(chunk_size),
            "total_chunks": str(total_chunks),
            "status": UploadStatus.UPLOADING.value
        }
        # pipeline = self.redis.pipeline()
        # pipeline.hset(meta_key, mapping=mapping)  # type: ignore
        # pipeline.expire(meta_key, self.ttl)  # type: ignore
        # pipeline.set(idx_key, upload_id, ex=self.ttl)
        # await pipeline.execute()
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(meta_key, mapping=mapping)
            pipe.expire(meta_key, self.ttl)
            pipe.set(idx_key, upload_id, ex=self.ttl)
            await pipe.execute()

        return UploadSession(
            upload_id=upload_id,
            user_id=str(user_id),
            file_name=file_name,
            file_hash=file_hash,
            file_ext=file_ext,
            mime_type=mime_type,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks
        )

    async def get_session(self, upload_id: str) -> UploadSession:
        meta_key = self._meta_key(upload_id)
        chunks_key = self._chunks_key(upload_id)
        # 1单次 RTT 批量拉起 Hash 与 Set
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.get(meta_key)
            pipe.smembers(chunks_key)
            raw_meta, chunks = await pipe.execute()
        if not raw_meta:
            raise ValueError(f"Unknown upload session: {upload_id}")
        # 2将数据转化为upload_session
        # 鲁棒性代码,防止有些字符串为空,导致pydantic无法转成None
        meta_dict = json.loads(raw_meta)
        uploaded_chunks = {int(chunk_index) for chunk_index in chunks}
        if "status" in meta_dict:
            meta_dict["status"] = UploadStatus(meta_dict["status"])
        return UploadSession(
            **meta_dict,
            uploaded_chunks=uploaded_chunks
        )

    # async def get_session(self, upload_id) -> UploadSession:
    #     meta_key = self._meta_key(upload_id)
    #     chunks_key = self._chunks_key(upload_id)
    #     async with self.redis.pipeline(transaction=False) as pipe:
    #         pipe.hgetall(meta_key)
    #         pipe.smembers(chunks_key)
    #         meta, chunks = await pipe.execute()
    #     if not meta:
    #         raise ValueError(f"Unknown upload session: {upload_id}")
    #     file_record_id = meta.get("file_record_id")
    #     return UploadSession(
    #         upload_id=meta["upload_id"],
    #         user_id=meta["user_id"],
    #         file_name=meta["file_name"],
    #         file_hash=meta["file_hash"],
    #         file_ext=meta["file_ext"],
    #         mime_type=meta["mime_type"],
    #         total_size=int(meta["total_size"]),
    #         chunk_size=int(meta["chunk_size"]),
    #         total_chunks=int(meta["total_chunks"]),
    #         status=meta.get("status", UploadStatus.UPLOADING.value),
    #         file_record_id = int(file_record_id) if file_record_id else None,
    #         error_msg=meta["error_msg"],
    #         uploaded_chunks={int(chunk_index) for chunk_index in chunks}
    #     )

    # async def add_uploaded_chunk(self, upload_id: str, chunk_index: int):
    #     meta_key = self._meta_key(upload_id)
    #     chunks_key = self._chunks_key(upload_id)
    #     if not await self.redis.exists(meta_key):
    #         raise ValueError(f"Unknown upload session: {upload_id}")
    #     async with self.redis.pipeline(transaction=True) as pipe:
    #         pipe.sadd(chunks_key, chunk_index)
    #         pipe.expire(chunks_key, self.ttl)
    #         pipe.expire(meta_key, self.ttl)
    #         await pipe.execute()
    async def add_uploaded_chunk(
            self,
            upload_id: str,
            user_id: int,
            chunk_index: int,
            file_hash: str,
    ):
        meta_k = self._meta_key(upload_id)
        chunks_k = self._chunks_key(upload_id)
        user_hash_k = self._user_hash_key(user_id, file_hash)
        res = await self.redis.eval(
            self.ADD_CHUNK_LUA,
            3,
            meta_k,
            chunks_k,
            user_hash_k,
            chunk_index,
            self.ttl
        )
        # 返回0表示当前上传会话不存在或已过期
        if res == 0:
            raise ValueError(f"Session not found: {upload_id}")
    async def compare_and_set_status(
            self,
            upload_id: str,
            user_id: int,
            file_hash: str,
            expected_status: UploadStatus,
            new_status: UploadStatus
    ) -> bool:
        meta_k = self._meta_key(upload_id)
        chunks_k = self._chunks_key(upload_id)
        user_hash_k = self._user_hash_key(user_id, file_hash)
        # CAS原子执行,通过是否更新成功判断是否抢到了执行权
        res = await self.redis.eval(
            self.CAS_STATUS_LUA,
            3,
            meta_k,
            user_hash_k,
            chunks_k,
            expected_status.value,
            new_status.value,
            time.time(),
            self.ttl
        )
        if res == -1:
            raise ValueError(f"Session not found:{upload_id}")
        return res == 1

    # async def set_status(
    #         self,
    #         upload_id: str,
    #         status: UploadStatus,
    #         file_record_id: int | None = None,
    #         error_msg: str | None = None
    # ):
    #     meta_key = self._meta_key(upload_id)
    #     mapping = {"status": status.value}
    #     if file_record_id is not None:
    #         mapping["file_record_id"] = str(file_record_id)
    #     if error_msg is not None:
    #         mapping["error_msg"] = error_msg
    #     await self.redis.hset(meta_key, mapping=mapping)

    async def set_completed(self, upload_id: str, file_record_id: int):
        await self.redis.eval(
            self.SET_FINAL_STATUS_LUA,
            1,
            self._meta_key(upload_id),
            UploadStatus.COMPLETED.value,
            str(file_record_id),
            "",
            time.time(),
            self.ttl
        )
    async def set_failed(self, upload_id: str, error_msg: str):
        await self.redis.eval(
            self.SET_FINAL_STATUS_LUA,
            1,
            self._meta_key(upload_id),
            UploadStatus.FAILED.value,
            "",
            error_msg,
            time.time(),
            self.ttl
        )


async def get_session_manager(
        redis: Redis = Depends(get_redis)
):
    return SessionManager(redis)
