import asyncio
import os
from typing import AsyncGenerator

import aiofiles.os
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi import Depends, UploadFile, HTTPException, status

from app.file.session_manager import UploadStatus
from app.file.session_manager import SessionManager, get_session_manager, UploadSession
from app.file.base_storage import BaseStorage
from app.file.storage_factory import get_storage
from app.file.key_builder import build_tmp_path, build_final_path
from app.crud.upload_crud import upload_crud
from app.core.config import settings
from app.models.base import FileRecord
from app.tasks.merge_tasks import merge_file
from pathlib import Path
import uuid




class UploadService:

    def __init__(
            self,
            storage: BaseStorage = Depends(get_storage),
            session_manager: SessionManager = Depends(get_session_manager),
    ):
        self.storage = storage
        self.session_manager = session_manager

    def _safe_unlink(self, path: Path):
        path.unlink(missing_ok=True)

    async def init_file_upload(
            self,
            user_id: int,
            file_name: str,
            file_hash: str,
            file_ext: str,
            mime_type: str,
            total_size: int,
            chunk_size: int,
            total_chunks: int,
            db: AsyncSession
    ) -> tuple[UploadSession | None, FileRecord | None]:
        # 先检查是否已存在相同文件
        file_record = await upload_crud.get_file_record_by_hash(db, file_hash)
        # 存在则可直接返回记录,实现秒传
        if file_record is not None:
            return None, file_record
        file_meta = {
            "file_name": file_name,
            "file_hash": file_hash,
            "file_ext": file_ext,
            "mime_type": mime_type,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks
        }
        # 幂等实现(同一用户多次相同操作识别)和并发安全
        # 想像有两个相同操作同时进行
        # 基于Redis的CAS原始操作
        # 返回: (session, is_new_created)
        session, is_new_created = await self.session_manager.get_or_create_session(
            user_id=user_id,
            upload_id_generator=lambda: uuid.uuid4().hex,
            file_data=file_meta
        )
        return session, None

    async def upload_file_chunk(
            self,
            upload_id: str,
            user_id: int,
            chunk_index: int,
            chunk_file: AsyncGenerator[bytes, None]
    ):
        # 上传文档,需要保证文本块重复上传时不会发生并发冲突,因此需要原子级文本块写入
        # 在调用上传接口之前先要进行校验一下chunk_index是否正确
        # 获取状态
        session = await self.get_status(upload_id, user_id)
        if session.status != UploadStatus.UPLOADING:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot upload chunks in {session.status.value}"
            )
        if chunk_index >= session.total_chunks or chunk_index < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Chunk index {chunk_index} out of bounds (total_chunks: {session.total_chunks})"
            )
        if chunk_index in session.uploaded_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Chunk index {chunk_index} has already been uploaded"
            )
        # 这里还真得添加校验逻辑检查是否已经上次过,否则可能和合并过程产生并发安全
        # 检验完成后,开始进行分片的上传
        # 这里为了保证并发安全,要做原子性写入
        true_tmp_chunk_path = build_tmp_path(upload_id=upload_id, chunk_index=chunk_index)
        # 临时路径,以保证同一请求同时到达的并发安全
        fake_tmp_chunk_path = true_tmp_chunk_path.with_name(f"{chunk_index}.{uuid.uuid4().hex}")
        try:
            # uuid生成路径保证不会重复
            await self.storage.upload_chunk(chunk_path=fake_tmp_chunk_path, file=chunk_file)
        except Exception as e:
            # 网络异常传输中断的情况下,清理未完成的垃圾分片
            # 这是使用同步API进行判断是因为aiofiles是假异步
            # 实际上是在线程池里跑,线程切换开销比同步API耗时还长
            if os.path.exists(fake_tmp_chunk_path):
                await aiofiles.os.remove(fake_tmp_chunk_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stream and write chunk data: {str(e)}"
            )
        try:
            # 临时文件分片写入后,进行原子替换,保证并发安全
            await aiofiles.os.replace(fake_tmp_chunk_path, true_tmp_chunk_path)
        except PermissionError:
            # 这是Windows系统下并发替换分片可能报的错误
            # Linux系统不会
            # 存在真实分片,说明是并发问题
            if os.path.exists(true_tmp_chunk_path):
                # 将当前报错的临时分片删除
                await aiofiles.os.remove(fake_tmp_chunk_path)
                print("Windows系统发生分片并发原子替换异常")
            # 不存在说明是真实系统权限问题
            else:
                if os.path.exists(fake_tmp_chunk_path):
                    await aiofiles.os.remove(fake_tmp_chunk_path)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"File system permission denied while saving chunk"
                )
        # 这是未知异常,仍然要将临时分片清理了
        except Exception as e:
            if os.path.exists(fake_tmp_chunk_path):
                await aiofiles.os.remove(fake_tmp_chunk_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected disk error: {str(e)}"
            )

        try:
            # 分片上传成功后,进行状态更新
            await self.session_manager.add_uploaded_chunk(
                upload_id=upload_id,
                chunk_index=chunk_index,
                user_id=user_id,
                file_hash=session.file_hash
            )
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown upload session: {upload_id}")
        except Exception:
            # 捕获未知异常,保证临时文件不残余
            await asyncio.to_thread(fake_tmp_chunk_path.unlink, missing_ok=True)
            # 同时抛出异常,以免遗漏(可被FastAPI全局异常捕获),以支持迭代开发捕获新的特定异常
            raise
    # async def merge_chunks(self, upload_id: str, db: AsyncSession) -> FileRecord:
    #     try:
    #         session = await self.session_manager.get_session(upload_id=upload_id)
    #     except ValueError:
    #         raise HTTPException(status_code=404, detail=f"Unknown upload session: {upload_id}")
    #     total_chunks = session.total_chunks
    #     source_paths = [build_tmp_path(upload_id, i) for i in range(total_chunks)]
    #     target_path = build_final_path(upload_id, session.file_name)
    #     await self.storage.merge_chunks(source_paths=source_paths, target_path=target_path)
    #     file_record = await upload_crud.create_upload(
    #         db=db,
    #         storage_type=settings.storage_type,
    #         storage_key=str(target_path),
    #         total_size=session.total_size,
    #         file_hash=session.file_hash,
    #         file_ext=session.file_ext,
    #         mime_type=session.mime_type
    #     )
    #     await db.commit()
    #     return file_record

    async def trigger_merge(self, upload_id: str, user_id: int) -> tuple[UploadStatus, str | None]:

        session = await self.get_status(upload_id, user_id)
        if session.status == UploadStatus.COMPLETED:
            return UploadStatus.COMPLETED, None
        # 精确完整性校验,必须严格等于[0,total_chunks-1]的完整集合
        expected_chunks = set(range(session.total_chunks))
        if session.uploaded_chunks != expected_chunks:
            missing_chunks = expected_chunks - session.uploaded_chunks
            raise HTTPException(
                status_code=400,
                detail=f"Chunks incomplete. Missing: {list(missing_chunks)}"
            )
        try:
            # 校验成功后,原子化CAS修改状态,以保证并发安全
            cas_success = await self.session_manager.compare_and_set_status(
                upload_id=upload_id,
                user_id=session.user_id,
                file_hash=session.file_hash,
                expected_status=UploadStatus.UPLOADING,
                new_status=UploadStatus.MERGING
            )
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown upload session: {upload_id}")
        if not cas_success:
            raise HTTPException(
                status_code=409,
                detail=f"Task is already in {UploadStatus.MERGING} state"
            )

        task = await merge_file.kiq(upload_id=upload_id)
        return UploadStatus.MERGING, task.task_id



    async def get_status(self, upload_id: str, user_id: int) -> UploadSession:
        try:
            session = await self.session_manager.get_session(upload_id=upload_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown upload session: {upload_id}"
            )
        # 进行权限校验
        if session.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: Not the owner of this upload session"
            )
        return session

