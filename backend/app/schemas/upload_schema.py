from enum import Enum

from pydantic import BaseModel, Field


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


# class InitUploadResponse(BaseModel):
#     is_completed: bool
#     upload_id: str | None = None
#     file_record_id: int | None = None
#     uploaed_chunks: set[int] = Field(default_factory=set)

    # uploaded_chunks: set[int] = set() 虽然Pydantic可以这么写,但是规范起见


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
