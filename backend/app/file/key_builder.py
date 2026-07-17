from app.core.config import settings
from pathlib import Path

def build_tmp_path(upload_id: str, chunk_index: int) -> Path:

    return settings.upload_tmp_dir / upload_id / f"{chunk_index:04d}"


def build_final_path(upload_id: str, filename: str) -> Path:

    suffix = ""
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[1]

    return settings.file_root_dir / upload_id[:2] / upload_id[2:4] / (upload_id + suffix)
