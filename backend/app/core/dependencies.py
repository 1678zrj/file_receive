from functools import lru_cache

from app.core.config import settings
from app.filecenter.interfaces import StorageBackend
from app.filecenter.key_builder import StorageKeyBuilder
from app.filecenter.chunked_manager import ChunkedUploadManager
from app.filecenter.storage.local import LocalStorage


# -- 单例工厂 --

@lru_cache
def _build_storage() -> StorageBackend:
    return LocalStorage(root_dir=settings.storage_root)


@lru_cache
def _build_key_builder() -> StorageKeyBuilder:
    return StorageKeyBuilder()


# -- FastAPI Depends --

def get_storage() -> StorageBackend:
    return _build_storage()


def get_key_builder() -> StorageKeyBuilder:
    return _build_key_builder()


# ChunkedUploadManager 有状态（内存会话），用单例保证会话一致性
_chunked_manager: ChunkedUploadManager | None = None


def get_chunked_manager() -> ChunkedUploadManager:
    global _chunked_manager
    if _chunked_manager is None:
        _chunked_manager = ChunkedUploadManager(
            storage=_build_storage(),
            key_builder=_build_key_builder(),
        )
    return _chunked_manager
