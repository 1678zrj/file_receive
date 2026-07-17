import math
import uuid
from pathlib import PurePosixPath
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

from app.filecenter.interfaces import StorageBackend
from app.filecenter.key_builder import StorageKeyBuilder
from app.filecenter.storage_result import StorageResult


@dataclass
class UploadSession:
    """上传会话元数据"""
    session_id: str
    filename: str
    namespace: str
    total_size: int
    chunk_size: int
    total_chunks: int
    # 已上传完成的分片索引集合
    uploaded_chunks: set[int] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)


class ChunkedUploadManager:
    """断点续传管理器（分片索引模式）

    每个分片独立存储为一个文件，支持：
    - 乱序上传 —— 客户端可以按任意顺序发送分片
    - 并发上传 —— 多个分片同时写入互不冲突
    - 精确续传 —— 只补传缺失的分片索引，不重传已有分片
    - 流式写入 —— 分片通过 AsyncIterator 小块异步读取，不全部加载到内存

    会话状态目前保存在内存中，后续可替换为 Redis 或数据库。
    """

    def __init__(
            self,
            storage: StorageBackend,
            key_builder: StorageKeyBuilder
    ):
        self._storage = storage
        self._key_builder = key_builder
        self._sessions: dict[str, UploadSession] = {}

    # -- 内部工具 --

    @staticmethod
    def _chunk_key(session_id: str, chunk_index: int) -> PurePosixPath:
        """单个分片文件的 key，用 4 位零填充保证字典序"""
        return PurePosixPath("_uploads", session_id, f"{chunk_index:04d}")

    # -- 公开 API --

    async def init_upload(
            self,
            filename: str,
            namespace: str,
            total_size: int,
            chunk_size: int
    ) -> UploadSession:
        """初始化一个断点续传会话"""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if total_size <= 0:
            raise ValueError("total_size must be positive")

        session_id = uuid.uuid4().hex
        total_chunks = math.ceil(total_size / chunk_size)
        session = UploadSession(
            session_id=session_id,
            filename=filename,
            namespace=namespace,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
        )
        self._sessions[session_id] = session
        return session

    async def upload_chunk(
            self,
            session_id: str,
            chunk_index: int,
            stream: AsyncIterator[bytes]
    ) -> None:
        """上传一个分片（流式写入）。可乱序调用，重复上传同一索引会覆盖（幂等）。

        stream 会被异步逐块读取写入，不会将整个分片加载到内存。

        Raises:
            ValueError: 会话不存在或 chunk_index 越界
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown upload session: {session_id}")
        if not (0 <= chunk_index < session.total_chunks):
            raise ValueError(
                f"chunk_index {chunk_index} out of range "
                f"[0, {session.total_chunks - 1}]"
            )

        chunk_key = self._chunk_key(session_id, chunk_index)
        await self._storage.put(chunk_key, stream)
        session.uploaded_chunks.add(chunk_index)

    async def get_session(
            self,
            session_id: str
    ) -> UploadSession:
        """获取会话详情"""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown upload session: {session_id}")
        return session

    async def list_sessions(
            self,
            namespace: str | None = None
    ) -> list[UploadSession]:
        """列出活跃会话，可按 namespace 过滤"""
        sessions = list(self._sessions.values())
        if namespace is not None:
            sessions = [s for s in sessions if s.namespace == namespace]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    async def get_progress(
            self,
            session_id: str
    ) -> dict:
        """查询上传进度

        Returns:
            {
                "uploaded_chunks": [0, 1, 3, ...],
                "missing_chunks":  [2, 4, ...],
                "total_chunks": 5,
                "complete": False,
            }
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown upload session: {session_id}")

        uploaded = sorted(session.uploaded_chunks)
        all_indices = set(range(session.total_chunks))
        missing = sorted(all_indices - session.uploaded_chunks)
        return {
            "uploaded_chunks": uploaded,
            "missing_chunks": missing,
            "total_chunks": session.total_chunks,
            "complete": len(missing) == 0,
        }

    async def complete_upload(
            self,
            session_id: str
    ) -> StorageResult:
        """完成上传：按索引顺序合并全部分片 → 迁入正式 key → 清理临时文件"""
        session = self._sessions.pop(session_id, None)
        if session is None:
            raise ValueError(f"Unknown upload session: {session_id}")

        if len(session.uploaded_chunks) < session.total_chunks:
            raise ValueError(
                f"Upload incomplete: "
                f"{len(session.uploaded_chunks)}/{session.total_chunks} chunks"
            )

        chunk_keys = [
            self._chunk_key(session_id, i)
            for i in range(session.total_chunks)
        ]
        final_key = self._key_builder.build(
            filename=session.filename,
            namespace=session.namespace,
        )

        # 合并
        await self._storage.concat(chunk_keys, final_key)

        # 清理分片文件
        for ck in chunk_keys:
            await self._storage.delete(ck)

        return StorageResult(
            key=final_key,
            size=session.total_size,
        )
