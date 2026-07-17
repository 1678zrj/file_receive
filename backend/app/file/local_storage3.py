from fastapi import UploadFile


from app.file.base_storage import BaseStorage
from app.core.config import settings

import aiofiles
import aiofiles.os
from pathlib import Path

# 该版本尝试的优化方案为使用同步代码跑以下的文件读写，防止线程太多导致异步主线程崩溃

class LocalStorage(BaseStorage):
    def __init__(self):
        self.stream_chunk_size = settings.stream_chunk_size


    async def upload_chunk(self, chunk_path: Path, file: UploadFile):

        await aiofiles.os.makedirs(chunk_path.parent, exist_ok=True)
        async with aiofiles.open(chunk_path, mode="wb") as f:
            while True:
                chunk = await file.read(self.stream_chunk_size)
                if not chunk:
                    break
                await f.write(chunk)

    async def merge_chunks(self, source_paths: list[Path], target_path: Path):
        await aiofiles.os.makedirs(target_path.parent, exist_ok=True)
        async with aiofiles.open(target_path, mode="wb") as wf:
            for tmp_chunk_path in source_paths:
                async with aiofiles.open(tmp_chunk_path, mode="rb") as rf:
                    while True:
                        chunk = await rf.read(self.stream_chunk_size)
                        if not chunk:
                            break
                        await wf.write(chunk)
