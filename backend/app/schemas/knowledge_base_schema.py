from datetime import datetime

from pydantic import BaseModel, Field


class CourseFileIndexRequest(BaseModel):
    title: str
    file_record_id: int
    course_id: int
    scope: str = "course"
    splitter_type: str = "markdown"
    chunk_size: int = Field(default=1024, ge=256, le=1536)



class CourseFileIndexResponse(BaseModel):
    id: int
    title: str
    file_record_id: int
    scope: str
    scope_id: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
