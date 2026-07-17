from typing import Protocol, AsyncIterator
from pathlib import PurePosixPath


class StorageBackend(Protocol):

    # -- 整文件操作 --

    async def save(
            self,
            key: PurePosixPath,
            stream: AsyncIterator[bytes]
    ) -> None:
        """保存完整文件流到指定 key"""
        ...

    async def open(
            self,
            key: PurePosixPath
    ) -> AsyncIterator[bytes]:
        """以流式读取文件"""
        ...

    async def delete(
            self,
            key: PurePosixPath
    ) -> None:
        """删除文件"""
        ...

    async def exists(
            self,
            key: PurePosixPath
    ) -> bool:
        """文件是否存在"""
        ...

    async def move(
            self,
            src: PurePosixPath,
            dst: PurePosixPath
    ) -> None:
        """将文件从 src 移动到 dst，dst 父目录需自动创建"""
        ...

    # -- 分片上传支持 --

    async def put(
            self,
            key: PurePosixPath,
            stream: AsyncIterator[bytes]
    ) -> None:
        """流式写入单个分片文件"""
        ...

    async def concat(
            self,
            sources: list[PurePosixPath],
            dest: PurePosixPath
    ) -> None:
        """按顺序将多个源文件合并拼接写入 dest"""
        ...

    async def hash(
            self,
            key: PurePosixPath,
            algorithm: str = "sha256"
    ) -> str:
        """计算文件的哈希值（十六进制字符串），用于内容寻址存储"""
        ...
