from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    model_config = {
        "env_prefix": "FR_",
        "env_file": BASE_DIR / ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    # -- 应用 --
    app_name: str = "File Receive"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./study.db"
    # -- 存储 --
    file_root_dir: Path = Path("data/storage/")
    # 上传临时目录（相对于 storage_root）
    upload_tmp_dir: Path = Path("data/tmp/")

    storage_type: str = "local"
    # -- 上传限制 --
    chunk_size: int = 5 * 1024 * 1024     # 默认分片大小 5 MB
    max_file_size: int = 2 * 1024 * 1024 * 1024  # 单文件最大 2 GB

    # -- 会话 --
    session_ttl_seconds: int = 3600 * 24  # 上传会话过期时间 24 小时

    # --流式读取 UploadFile 的缓冲区大小（1MB）--
    stream_chunk_size: int = 1 * 1024 * 1024

    # -- Redis -- 配置
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_max_connections: int = 500
    redis_socket_keepalive: bool = True

    # -- 鉴权 --
    secret_key: str = "test"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 1

    # -- 业务命名空间白名单 --
    # 只有在此列表中的 namespace 才允许作为存储路径前缀
    # 通过环境变量 FR_ALLOWED_NAMESPACES 配置，逗号分隔，例如：
    #   FR_ALLOWED_NAMESPACES=avatar,submission,courseware
    allowed_namespaces: list[str] = ["avatar", "submission", "courseware", "material"]


settings = Settings()
# print(settings)
# print(Path(__file__).resolve())
# print(Path(__file__).resolve().parent)