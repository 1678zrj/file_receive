from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field
from app.models.base import utc_now


class KnowledgeDocument(SQLModel, table=True):
    __tablename__ = "knowledge_document"
    __table_args__ = (UniqueConstraint("file_hash", "scope_id", name="uq_file_scope"),)
    id: int = Field(default=None, primary_key=True)
    file_record_id: int = Field(foreign_key="file_record.id")
    file_hash: str = Field(description="该文件的hash值,sha256")
    scope: str
    scope_id: str
    chunk_count: int
    created_at: datetime = Field(default_factory=utc_now)

#
# class KnowledgeDocumentChunk(SQLModel, table=True):
#     id: int = Field(default=None, primary_key=True)
#
#     pass
