from abc import ABC, abstractmethod
from typing import AsyncGenerator
from pathlib import Path



class BaseStorage(ABC):

    @abstractmethod
    async def upload_chunk(self, chunk_path: Path, file: AsyncGenerator[bytes, None]):
        ...

    @abstractmethod
    async def merge_chunks(self, source_paths: list[Path], target_path: Path):
        pass