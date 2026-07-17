import asyncio
from pathlib import Path, PurePosixPath
from typing import AsyncIterator

import aiofiles

from app.filecenter.interfaces import StorageBackend


class LocalStorage(StorageBackend):

    def __init__(self, root_dir: str | Path):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: PurePosixPath) -> Path:
        return self.root / Path(str(key))

    # -- 整文件操作 --
    async def save(
            self,
            key: PurePosixPath,
            stream: AsyncIterator[bytes]
    ) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, 'wb') as f:
            async for chunk in stream:
                await f.write(chunk)

    async def open(
            self,
            key: PurePosixPath
    ) -> AsyncIterator[bytes]:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        async with aiofiles.open(path, 'rb') as f:
            while True:
                chunk = await f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    async def delete(
            self,
            key: PurePosixPath
    ) -> None:
        path = self._resolve(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)

    async def exists(
            self,
            key: PurePosixPath
    ) -> bool:
        path = self._resolve(key)
        return path.exists()

    async def move(
            self,
            src: PurePosixPath,
            dst: PurePosixPath
    ) -> None:
        src_path = self._resolve(src)
        dst_path = self._resolve(dst)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(src_path.rename, dst_path)

    # -- 分片上传支持 --

    async def put(
            self,
            key: PurePosixPath,
            stream: AsyncIterator[bytes]
    ) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, 'wb') as f:
            async for chunk in stream:
                await f.write(chunk)

    async def concat(
            self,
            sources: list[PurePosixPath],
            dest: PurePosixPath
    ) -> None:
        dest_path = self._resolve(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(dest_path, 'wb') as outf:
            for src in sources:
                src_path = self._resolve(src)
                if not src_path.exists():
                    raise FileNotFoundError(f"Chunk missing: {src}")
                async with aiofiles.open(src_path, 'rb') as inf:
                    while True:
                        chunk = await inf.read(1024 * 1024)
                        if not chunk:
                            break
                        await outf.write(chunk)
