import asyncio

import aiofiles
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
from app.models.rag import KnowledgeDoc, DocumentStatus
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from app.core.config import settings


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
        self.rag_markdown_storage_dir = settings.rag_markdown_storage_dir


    def _build_markdown_storage_key(
            self,
            scope: str,
            scope_id: str,
            knowledge_doc_id: int
    ) -> tuple[Path, str]:
        relative_path = f"scope_{scope}/{scope_id}/doc_{knowledge_doc_id}.md"
        return self.rag_markdown_storage_dir / relative_path, relative_path




    # 该函数专用于上传文件到向量数据库
    # 不用于更新已存在向量数据库中的某文件，那个实现逻辑更加复杂
    async def index_course_file(
            self,
            title: str,
            file_record_id: int,
            course_id: int,
            teacher_id: int,
            scope: str = "course",
            splitter_type: str = "markdown",
            chunk_size: int = 1024
    ) -> KnowledgeDoc:
        # 先进行鉴权，查看当前用户是否有权限进行修改
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
        # 权限鉴定通过后，再查看原始文档是否已经存在
        raw_file_record = await upload_crud.get_file_record_by_id(self.db, file_record_id)
        if raw_file_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文件记录 ID {file_record_id} 不存在"
            )
        kb_doc: KnowledgeDoc
        # 以上操作过后，开始进行并发安全校验
        # 设想两个可以视为同时进行的操作
        # 大家首先检查KnowledgeDoc表中是否已经有了当前知识库中文件的记录了
        scope_id = f"{scope}_{course_id}"
        existing_kb_doc = await knowledge_base_crud.get_kb_doc(
            db=self.db,
            file_record_id=file_record_id,
            scope=scope,
            scope_id=scope_id
        )
        # 先粗分为已存在和不存在
        if existing_kb_doc:
            # 存在的情况得分状态讨论
            # 1、已存在且状态为成功
            if existing_kb_doc.status == DocumentStatus.SUCCESS:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"该文件已在此课程知识库中成功建立索引，请勿重复操作"
                )
            # 2、已存在且正在进行解析、分块、向量化中的任何一步（这里假定的是状态在这些情况都是正常进行的，而不是异常终止的）
            elif existing_kb_doc.status in (
                DocumentStatus.CHUNKING,
                DocumentStatus.INDEXING,
                DocumentStatus.PARSING
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="该文件已在此课程知识库中成功建立索引，请勿重复操作"
                )
            # 3、查询到当前文档在解析过程中失败了，这个时候必然是要重新解析的
            # 这种情况下，两个可以视为同时进行的操作必然进行争夺，因为两个完全相同的请求只有一个可以进行处理
            elif existing_kb_doc.status == DocumentStatus.FAILED:
                # 这里利用数据库的单行排他锁（即数据库自带锁），通过查看当前更新操作影响的数量来判断谁抢到了
                row_count = await knowledge_base_crud.update_kb_doc_failed_status(
                    self.db,
                    id = existing_kb_doc.id
                )
                if row_count == 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="任务正在被另一个并发请求重试处理中，请勿重复提交"
                    )
                # 运行到这里说明抢到了执行权，抢到执行权只会要做的先是失败的善后工作
                kb_doc = await knowledge_base_crud.get_kb_doc_by_id(self.db, existing_kb_doc.id)
                # 第一个是Knowledge_doc_Chunk表中可能存在残存的记录，需要删除
                await knowledge_base_crud.delete_chunk_by_doc_id(self.db, kb_doc.id)
                await self.db.commit()
                # 第二个是删除向量数据库中的残余记录
                await self.vector_store.delete_by_doc_id(kb_doc.id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"未知文档状态: {existing_kb_doc.status}"
                )
        else:
            # 不存在相关记录
            # 这种情况下，两个可以视为同时进行的操作必然进行争夺，因为两个完全相同的请求只有一个可以进行处理
            # 这里可以利用数据库唯一索引插入数据来进行争夺
            kb_doc_data = {
                "title": title,
                "file_record_id": file_record_id,
                "scope": scope,
                "scope_id": scope_id,
                "created_by": teacher_id,
                "status": DocumentStatus.PARSING
            }
            try:
                kb_doc = await knowledge_base_crud.create_kb_doc(
                    self.db,
                    kb_doc_data
                )
                await self.db.commit()
            # 利用数据库的唯一索引报错来判断是否抢到了执行权
            except IntegrityError as e:
                await self.db.rollback()
                # 没抢到执行权，报异常
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="并发创建冲突，该任务已由另一个请求创建并正在处理中"
                )
        # 执行到这里，前面的一系列权限和并发安全操作都做完了，可以正经写业务代码了
        try:
            # 第一步是文档解析
            # 如果markdown文件已经存在,则可以不用解析,直接读取,否则解析并持久化存储
            if kb_doc.markdown_storage_key is None:
                raw_file_path = Path(raw_file_record.storage_key)
                async with ayafileio.open(raw_file_path, mode='rb') as f:
                    file_bytes = await f.read()
                file_parser = self.rag_container.get_parser(raw_file_record.file_ext)
                markdown_text = await asyncio.to_thread(file_parser.parse, file_bytes)
                if not markdown_text or not markdown_text.strip():
                    raise ValueError("文档解析出的markdown为空")
                markdown_storage_key, relative_path = self._build_markdown_storage_key(
                    scope=scope,
                    scope_id=scope_id,
                    knowledge_doc_id=kb_doc.id
                )
                await aiofiles.os.makedirs(markdown_storage_key.parent, exist_ok=True)
                async with ayafileio.open(markdown_storage_key, mode='w', encoding='utf-8') as f:
                    await f.write(markdown_text)
                kb_doc.markdown_storage_key = markdown_storage_key
            else:
                markdown_file_path = self.rag_markdown_storage_dir / kb_doc.markdown_storage_key
                async with ayafileio.open(markdown_file_path, mode='r', encoding='utf-8') as f:
                    markdown_text = await f.read()
            kb_doc.status = DocumentStatus.CHUNKING
            self.db.add(kb_doc)
            await self.db.commit()
            # 获取到了原始文档解析后的markdown文本,接下来进行文本切分
            splitter = self.rag_container.get_splitter(splitter_type)
            chunk_texts: list[str] = await asyncio.to_thread(
                splitter.split_text,
                markdown_text,
                chunk_size
            )
            if not chunk_texts:
                raise ValueError(f"未能从文档中切分出有效文本块")
            kb_doc.status = DocumentStatus.INDEXING
            self.db.add(kb_doc)
            await self.db.commit()
            # 开始进行向量化
            dense_vectors = await self.embedder.embed_documents(chunk_texts)
            vector_insert_res = await self.vector_store.upsert(
                dense_vectors=dense_vectors,
                chunk_texts=chunk_texts,
                knowledge_doc_id=kb_doc.id,
                file_record_id=file_record_id,
                file_hash=raw_file_record.file_hash,
                scope=scope,
                scope_id=scope_id,
                is_enabled=True
            )
            vector_ids = vector_insert_res.get("ids")
            kb_doc_chunk_data_list = [
                {
                    "knowledge_doc_id": kb_doc.id,
                    "vector_id": vector_ids[chunk_index],
                    "chunk_text": chunk_text,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk_text) // 3,
                    "is_enabled": True
                }
                for chunk_index, chunk_text in enumerate(chunk_texts)
            ]

            knowledge_doc_chunks = await knowledge_base_crud.create_kb_doc_chunks(
                db=self.db,
                kb_doc_chunk_data_list=kb_doc_chunk_data_list
            )
            kb_doc.status = DocumentStatus.SUCCESS
            kb_doc.error_msg = None
            self.db.add(kb_doc)
            await self.db.commit()
            await self.db.refresh(kb_doc)
            return kb_doc
        except Exception as e:
            await self.db.rollback()
            kb_doc.status = DocumentStatus.FAILED
            kb_doc.error_msg = str(e)
            self.db.add(kb_doc)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"知识库构建失败:{str(e)}"
            )


