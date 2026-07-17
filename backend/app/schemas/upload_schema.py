from pydantic import BaseModel


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
    uploaded_chunks: set[int]
    total_chunks: int

class MergeChunksResponse(BaseModel):
    status: str
    file_record_id: int
    storage_key: str