from abc import ABC, abstractmethod
from fastapi import UploadFile
from pathlib import Path



class BaseStorage(ABC):

    @abstractmethod
    async def upload_chunk(self, chunk_path: Path, file: UploadFile):
        ...

    @abstractmethod
    async def merge_chunks(self, source_paths: list[Path], target_path: Path):
        pass