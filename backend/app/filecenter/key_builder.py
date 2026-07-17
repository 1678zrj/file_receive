from pathlib import PurePosixPath
from uuid import uuid4


class StorageKeyBuilder:
    """存储 key 构建器。

    用 UUID 前 4 位做两级目录散列，避免单目录文件数过多。
    每次调用生成独立 key —— 同一文件上传两次 = 两个独立副本。
    """

    def build(
            self,
            filename: str,
            namespace: str
    ) -> PurePosixPath:
        suffix = ""
        if "." in filename:
            suffix = "." + filename.rsplit(".", 1)[1]
        uid = uuid4().hex
        return PurePosixPath(
            namespace,
            uid[:2],
            uid[2:4],
            uid + suffix,
        )
