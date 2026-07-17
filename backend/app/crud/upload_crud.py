from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.table import FileRecord

class UploadCRUD:

    async def create_upload(
            self,
            db: AsyncSession,
            storage_type: str,
            storage_key: str,
            total_size: int,
            file_hash: str,
            file_ext: str | None = None,
            mime_type: str | None = None,
    ) -> FileRecord:
        upload_file = FileRecord(
            file_ext = file_ext,
            mime_type = mime_type,
            storage_type = storage_type,
            storage_key = storage_key,
            total_size = total_size,
            file_hash = file_hash
        )
        db.add(upload_file)
        await db.flush()
        return upload_file




upload_crud = UploadCRUD()
