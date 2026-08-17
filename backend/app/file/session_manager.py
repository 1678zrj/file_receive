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
    uploaded_chunks: set[int] = field(default_factory=set)


class SessionManager:
    def __init__(self, redis_client: Redis, ttl: int = 86400):
        self.redis = redis_client
        self.prefix = "upload_session"
        self.ttl = ttl

    def _meta_key(self, upload_id: str) -> str:
        return f"{self.prefix}:{upload_id}:meta"

    def _chunks_key(self, upload_id: str) -> str:
        return f"{self.prefix}:{upload_id}:chunks"

    async def add_session(
            self,
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
        mapping = {
            "upload_id": upload_id,
            "file_name": file_name,
            "file_hash": file_hash,
            "file_ext": file_ext,
            "mime_type": mime_type,
            "total_size": str(total_size),
            "chunk_size": str(chunk_size),
            "total_chunks": str(total_chunks),
            "status": UploadStatus.UPLOADING
        }
        pipeline = self.redis.pipeline()
        pipeline.hset(meta_key, mapping=mapping)  # type: ignore
        pipeline.expire(meta_key, self.ttl)  # type: ignore
        await pipeline.execute()

        return UploadSession(
            upload_id=upload_id,
            file_name=file_name,
            file_hash=file_hash,
            file_ext=file_ext,
            mime_type=mime_type,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks
        )

    async def get_session(self, upload_id) -> UploadSession:
        meta_key = self._meta_key(upload_id)
        chunks_key = self._chunks_key(upload_id)
        pipeline = self.redis.pipeline()
        pipeline.hgetall(meta_key)
        pipeline.smembers(chunks_key)
        meta, chunks = await pipeline.execute()
        if not meta:
            raise ValueError(f"Unknown upload session: {upload_id}")
        file_record_id = meta.get("file_record_id") or None
        return UploadSession(
            upload_id=meta["upload_id"],
            file_name=meta["file_name"],
            file_hash=meta["file_hash"],
            file_ext=meta["file_ext"],
            mime_type=meta["mime_type"],
            total_size=int(meta["total_size"]),
            chunk_size=int(meta["chunk_size"]),
            total_chunks=int(meta["total_chunks"]),
            status=meta.get("status", UploadStatus.UPLOADING),
            file_record_id = int(file_record_id) if file_record_id else None,
            uploaded_chunks={int(chunk_index) for chunk_index in chunks}
        )

    async def add_uploaded_chunk(self, upload_id: str, chunk_index: int):
        meta_key = self._meta_key(upload_id)
        chunks_key = self._chunks_key(upload_id)
        if not await self.redis.exists(meta_key):
            raise ValueError(f"Unknown upload session: {upload_id}")
        pipeline = self.redis.pipeline()
        pipeline.sadd(chunks_key, chunk_index)
        pipeline.expire(chunks_key, self.ttl)
        pipeline.expire(meta_key, self.ttl)
        await pipeline.execute()

    async def set_status(
            self,
            upload_id: str,
            status: UploadStatus,
            file_record_id: int | None = None,
            error_msg: str | None = None
    ):
        meta_key = self._meta_key(upload_id)
        mapping = {"status": status}
        if file_record_id is not None:
            mapping["file_record_id"] = str(file_record_id)
        if error_msg is not None:
            mapping["error_msg"] = error_msg
        await self.redis.hset(meta_key, mapping=mapping)

    async def delete_session(self, upload_id: str):
        meta_key = self._meta_key(upload_id)
        chunks_key = self._chunks_key(upload_id)
        deleted_count = await self.redis.delete(meta_key, chunks_key)
        if deleted_count == 0:
            raise ValueError(f"Unknown upload session: {upload_id}")


async def get_session_manager(
        redis: Redis = Depends(get_redis)
):
    return SessionManager(redis)
