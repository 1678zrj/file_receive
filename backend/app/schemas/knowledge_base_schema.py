from pydantic import BaseModel, Field


class CourseFileIndexRequest(BaseModel):
    file_record_id: int
    course_id: int
    scope: str = "course"
    splitter_type: str = "markdown"
    chunk_size: int = Field(default=1024, ge=256, le=1536)


class CourseFileIndexResponse(BaseModel):
    id: int
    file_record_id: int
    file_hash: str
    scope: str
    scope_id: str
    chunk_count: int