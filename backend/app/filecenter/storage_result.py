from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(slots=True)
class StorageResult:
    """
    FileCenter 唯一返回对象

    只描述“文件已经被存储成功”的事实，
    不包含任何业务信息（assignment / user / course）
    """
    key: PurePosixPath
    size: int
    hash: str | None = None