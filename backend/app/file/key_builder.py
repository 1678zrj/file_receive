from app.core.config import settings
from pathlib import Path


def build_storage_key(upload_id: str, filename: str) -> str:
    # suffix = ""
    # if "." in filename:
    #     suffix = "." + filename.rsplit(".", 1)[1]

    # 更健壮优雅的写法（自动处理无后缀、以点开头等边界）
    suffix = Path(filename).suffix
    return f"{upload_id[:2]}/{upload_id[2:4]}/{(upload_id + suffix)}"


def build_tmp_path(upload_id: str, chunk_index: int) -> Path:
    return settings.upload_tmp_dir / upload_id / f"{chunk_index:04d}"


def build_final_path(storage_key: str) -> Path:
    return settings.file_root_dir / storage_key
