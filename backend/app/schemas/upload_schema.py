from enum import Enum
from pydantic import BaseModel, Field


class UploadStatus(str, Enum):
    UPLOADING = "uploading"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


class InitUploadRequest(BaseModel):
    file_name: str = Field(..., description="原始文件名")
    file_hash: str = Field(..., description="全量文件HASH")
    file_ext: str = Field(..., description="文件扩展名")
    mime_type: str = Field(..., description="MIME类型")
    total_size: int = Field(gt=0, description="文件总字节数")
    chunk_size: int = Field(gt=0, description="分片大小")
    total_chunks: int = Field(gt=0, description="分片总数")


class InitUploadResponse(BaseModel):
    instant_upload: bool = Field(description="True表示秒传成功,无需传输分片")
    upload_id: str | None = Field(default=None, description="分片上传会话id")
    file_record_id: int | None = Field(default=None, description="物理文件ID(秒传或完成时返回)")
    uploaded_chunks: list[int] = Field(default_factory=list, description="已经上传的分片索引")

    # uploaded_chunks: set[int] = set() 虽然Pydantic可以这么写,但是规范起见


class UploadStatusResponse(BaseModel):
    upload_id: str
    status: UploadStatus
    uploaded_chunks: set[int]
    total_chunks: int
    file_record_id: int | None = None
    error_msg: str | None = None



class MergeTriggerResponse(BaseModel):
    upload_id: str
    task_id: str | None = Field(default=None, description="异步任务ID")
    status: UploadStatus
