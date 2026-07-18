from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi import Depends, UploadFile, HTTPException


from app.file.session_manager import SessionManager, get_session_manager, UploadSession
from app.file.base_storage import BaseStorage
from app.file.storage_factory import get_storage
from app.file.key_builder import build_tmp_path, build_final_path
from app.crud.upload_crud import upload_crud
from app.core.config import settings
from app.models.table import FileRecord

import uuid


class UploadService:

    def __init__(
            self,
            storage: BaseStorage = Depends(get_storage),
            session_manager: SessionManager = Depends(get_session_manager),
    ):
        self.storage = storage
        self.session_manager = session_manager


    async def init_file_upload(
            self,
            file_name: str,
            file_hash: str,
            file_ext: str,
            mime_type: str,
            total_size: int,
            chunk_size: int,
            total_chunks: int
    ) -> UploadSession:
        upload_id = uuid.uuid4().hex
        new_session = await self.session_manager.add_session(
            upload_id= upload_id,
            file_name= file_name,
            file_hash= file_hash,
            file_ext=file_ext,
            mime_type=mime_type,
            total_size= total_size,
            chunk_size= chunk_size,
            total_chunks= total_chunks
        )
        return new_session

    async def upload_file_chunk(self, upload_id: str, chunk_index: int, chunk_file: UploadFile):
        tmp_path = build_tmp_path(upload_id=upload_id, chunk_index=chunk_index)
        await self.storage.upload_chunk(chunk_path=tmp_path, file=chunk_file)
        try:
            await self.session_manager.add_uploaded_chunk(upload_id=upload_id, chunk_index=chunk_index)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown upload session: {upload_id}")


    async def merge_chunks(self, upload_id: str, db: AsyncSession) -> FileRecord:
        try:
            session = await self.session_manager.get_session(upload_id=upload_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown upload session: {upload_id}")
        total_chunks = session.total_chunks
        source_paths = [build_tmp_path(upload_id, i) for i in range(total_chunks)]
        target_path = build_final_path(upload_id, session.file_name)
        await self.storage.merge_chunks(source_paths=source_paths, target_path=target_path)
        file_record = await upload_crud.create_upload(
            db=db,
            storage_type=settings.storage_type,
            storage_key=str(target_path),
            total_size=session.total_size,
            file_hash=session.file_hash,
            file_ext=session.file_ext,
            mime_type=session.mime_type
        )
        await db.commit()
        return file_record



    async def get_status(self, upload_id: str) -> UploadSession:
        try:
            return await self.session_manager.get_session(upload_id=upload_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown upload session: {upload_id}")
