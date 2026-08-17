from typing import AsyncGenerator




from app.file.base_storage import BaseStorage
from app.core.config import settings

import aiofiles
import aiofiles.os
import ayafileio

from pathlib import Path
import asyncio
import shutil

upload_sem = asyncio.Semaphore(10)
merge_sem = asyncio.Semaphore(1)

class LocalStorage(BaseStorage):
    def __init__(self):
        self.stream_chunk_size = settings.stream_chunk_size

    async def file_stream_buffer(self, file: AsyncGenerator[bytes, None]) -> AsyncGenerator[bytes, None]:
        buffer_size = self.stream_chunk_size
        buffer_chunk = bytearray()
        async for chunk in file:
            buffer_chunk.extend(chunk)
            while len(buffer_chunk) >= buffer_size:
                yield buffer_chunk[:buffer_size]
                del buffer_chunk[:buffer_size]
        if buffer_chunk:
            yield buffer_chunk


    async def upload_chunk(self, chunk_path: Path, file: AsyncGenerator[bytes, None]):
        async with upload_sem:
            await aiofiles.os.makedirs(chunk_path.parent, exist_ok=True)
            async with ayafileio.open(chunk_path, mode="wb") as f:
                buffer = self.file_stream_buffer(file)
                async for chunk in buffer:
                    if chunk:
                        await f.write(chunk)

    # 1. 提取出来的同步合并方法
    def _sync_merge_chunks(self, source_paths: list[Path], target_path: Path):
        # 使用 pathlib 创建目录，exist_ok=True 避免已存在时报错
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用标准的同步 open
        with open(target_path, mode="wb") as wf:
            for tmp_chunk_path in source_paths:
                with open(tmp_chunk_path, mode="rb") as rf:
                    # 使用 shutil.copyfileobj 代替手动的 while True 读取
                    # length 参数指定每次读取的块大小，避免内存溢出
                    shutil.copyfileobj(rf, wf, length=self.stream_chunk_size)

    # 2. 原来的异步入口，使用 asyncio.to_thread 将其放入默认线程池执行
    async def merge_chunks(self, source_paths: list[Path], target_path: Path):
        # asyncio.to_thread 内部会自动使用底层的 ThreadPoolExecutor
        # 不会阻塞主事件循环，保证 upload_chunk 能顺畅接收网络数据

        await asyncio.to_thread(self._sync_merge_chunks, source_paths, target_path)

