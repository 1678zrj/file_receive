import enum
from datetime import datetime
from sqlalchemy import UniqueConstraint, Column, Enum, Text, BigInteger
from sqlmodel import SQLModel, Field
from app.models.base import utc_now, AwareCreatedAt, AwareUpdatedAt


class DocumentStatus(str, enum.Enum):
    PENDING = "PENDING"    #排队中，还没进入任务队列执行
    PARSING = "PARSING"    #正在进行解析
    CHUNKING = "CHUNKING"  #真正进行分块
    INDEXING = "INDEXING"  #正在插入向量数据库
    SUCCESS = "SUCCESS"    #成功
    FAILED = "FAILED"      #失败



# 一个知识库文件记录只对应一个物理文件实体（file_record）
# 但是一个物理文件实体可以对应多个知识库文件记录
# 因为不同的课程/用户的知识库中可能存同一份文件
class KnowledgeDoc(SQLModel, table=True):
    __tablename__ = "knowledge_doc"
    # 设计上是支持不同用户不同业务的知识库可以拥有同一份文档
    # 同一个用户的同一个业务的知识库则不能重复上传原始文档
    __table_args__ = (UniqueConstraint("file_record_id", "scope","scope_id", name="uq_file_scope"),)
    id: int = Field(default=None, primary_key=True)
    title: str = Field(description="文档在知识库中的展示标题")
    file_record_id: int = Field(foreign_key="file_record.id", description="上传的原始文件记录id")
    markdown_storage_key: str | None = Field(default=None, description="解析后的Markdown文件存储路径")
    markdown_char_count: int | None = Field(
        default=None,
        description="Markdown文本总字符数"
    )
    scope: str = Field(index=True, description="所属域：course（课程）/ personal（个人）")
    scope_id: str = Field(index=True, description="对应作用域的id，如course_1, user_5")
    created_by: int = Field(foreign_key="user.id", description="上传人/创建人ID")
    status: DocumentStatus = Field(
        default=DocumentStatus.PARSING,
        sa_column=Column(Enum(DocumentStatus)),
        description="文档处理状态"
    )
    error_msg: str | None = Field(
        default=None,
        description="失败时的错误堆栈信息"
    )
    chunk_count: int = Field(default=0, description="分块总数")
    is_enabled: bool = Field(default=True, description="是否启用检索")
    created_at: AwareCreatedAt
    updated_at: AwareUpdatedAt

# 知识库文档文本块是连接向量数据库和知识库文档表的桥梁
# 一个知识库文档记录可以有多个知识库文档分块记录
# 一个知识库文档分块记录则只能对应一个知识库文档
class KnowledgeDocChunk(SQLModel, table=True):
    __tablename__ = "Knowledge_doc_chunk"
    id: int = Field(default=None, primary_key=True)
    knowledge_doc_id: int = Field(foreign_key="knowledge_doc.id", index=True)
    vector_id: int = Field(sa_type=BigInteger, index=True, description="对应的向量数据库向量id")
    chunk_text: str = Field(sa_column=Column(Text) ,description="对应的文本块内容")
    chunk_index: int = Field(description="在所属文档的连续切片索引，用于连续还原和排序")
    token_count: int = Field(default=0, description="token的切片数量估算")
    is_enabled: bool = Field(default=True, description="单个切片是否启用（用于屏蔽脏数据）")
    created_at: AwareCreatedAt


