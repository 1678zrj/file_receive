from app.core.config import settings
from app.file.local_storage import LocalStorage
from app.file.base_storage import BaseStorage

class StorageFactory:

    @staticmethod
    def get_storage_engine(storage_type: str | None = None) -> BaseStorage:
        if storage_type is None:
            storage_type = settings.storage_type

        if storage_type == "local":
            return LocalStorage()


async def get_storage() -> BaseStorage:
    return StorageFactory.get_storage_engine()
