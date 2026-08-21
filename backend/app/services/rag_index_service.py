import asyncio
from sqlalchemy.exc import IntegrityError
from app.db.session import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends
from app.crud.upload_crud import upload_crud
from pathlib import Path
from app.core.rag_deps import get_rag
from app.rag.container import RAGContainer
from app.rag.embeddings.base import BaseEmbedder
from app.rag.vector_stores.base import BaseVectorStore
from app.core.rag_deps import get_embedder, get_vector_store
import ayafileio
from app.crud.knowledgebase_crud import knowledge_base_crud
from app.crud.course_crud import course_crud
from app.models.rag import KnowledgeDocument
from fastapi import HTTPException, status


class RAGIndexService:
    def __init__(
            self,
            rag_container: RAGContainer = Depends(get_rag),
            embedder: BaseEmbedder = Depends(get_embedder),
            vector_store: BaseVectorStore = Depends(get_vector_store),
            db: AsyncSession = Depends(get_session)
    ):

        self.db = db
        self.rag_container = rag_container
        self.embedder = embedder
        self.vector_store = vector_store


    # 该函数专用于上传文件到向量数据库
    # 不用于更新已存在向量数据库中的某文件，那个实现逻辑更加复杂
    async def index_course_file(
            self,
            file_record_id: int,
            course_id: int,
            teacher_id: int,
            scope: str,
            splitter_type: str = "markdown",
            chunk_size: int = 1024
    ) -> KnowledgeDocument:
        target_course = await course_crud.get_course_by_id(self.db, course_id)
        if target_course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"课程ID {course_id} 不存在"
            )
        if target_course.teacher_id != teacher_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权管理该课程的知识库"
            )
        file_record = await upload_crud.get_file_record_by_id(self.db, file_record_id)
        if file_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文件记录 ID {file_record_id} 不存在"
            )
        file_path = Path(file_record.storage_key)
        async with ayafileio.open(file_path, mode='rb') as f:
            file_bytes = await f.read()
        # 文档入库需要解析、分块、向量化、入库
        ext = file_record.file_ext
        file_parser = self.rag_container.get_parser(ext)
        text = await asyncio.to_thread(file_parser.parse, file_bytes)
        if not text or not text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件解析出的有效文本为空，无法构建知识库"
            )
        splitter = self.rag_container.get_splitter(splitter_type)
        chunk_texts = await asyncio.to_thread(splitter.split_text, text, chunk_size)
        if not chunk_texts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档未能切分出有效文本块"
            )
        dense_vectors = await self.embedder.embed_documents(chunk_texts)
        scope_id = f"{scope}_{course_id}"
        await self.vector_store.upsert(
            dense_vectors=dense_vectors,
            chunk_texts=chunk_texts,
            file_record_id=str(file_record_id),
            file_hash=file_record.file_hash,
            scope=scope,
            scope_id=scope_id
        )
        kb_doc_dict = {
            "file_record_id": file_record_id,
            "file_hash": file_record.file_hash,
            "scope": scope,
            "scope_id": scope_id,
            "chunk_count": len(chunk_texts)
        }
        try:
            new_kb_doc = await knowledge_base_crud.create_kb_document(self.db, kb_doc_dict)
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该文件已上传，请勿重复上传"
            )
        return new_kb_doc