from enum import Enum

from pydantic import BaseModel


class UploadStatus(str, Enum):
    UPLOADING = "uploading"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


class InitUploadRequest(BaseModel):
    file_name: str
    file_hash: str
    file_ext: str
    mime_type: str
    total_size: int
    chunk_size: int
    total_chunks: int


class InitUploadResponse(BaseModel):
    upload_id: str


class UploadStatusResponse(BaseModel):
    upload_id: str
    status: UploadStatus
    uploaded_chunks: set[int]
    total_chunks: int
    file_record_id: int | None = None


class MergeChunksResponse(BaseModel):
    status: str
    file_record_id: int
    storage_key: str


class MergeTriggerResponse(BaseModel):
    upload_id: str
    task_id: str
    status: UploadStatus = UploadStatus.MERGING
