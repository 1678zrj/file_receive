import shutil
from app.core.broker import broker
from app.crud.upload_crud import upload_crud
from app.file.local_storage2 import LocalStorage
from app.file.session_manager import get_session_manager, SessionManager
from app.file.storage_factory import get_storage
import asyncio
from app.file.key_builder import build_tmp_path, build_final_path
from app.db.session import AsyncSessionLocal
from app.core.config import settings
from app.redis.redis_client import RedisManager
from app.schemas.upload_schema import UploadStatus
@broker.task(task_name="merge_file_task")
async def merge_file(
    upload_id: str
):
    """当前文档还是以绝对路径存储在数据库中，未来需要修改"""
    storage = LocalStorage()
    session_manager = SessionManager(redis_client=RedisManager.get_client())
    session = await session_manager.get_session(upload_id)
    total_chunks = session.total_chunks
    source_paths = [build_tmp_path(upload_id, i) for i in range(total_chunks)]
    target_path = build_final_path(upload_id, session.file_name)
    async with AsyncSessionLocal() as db:
        try:
            # 将文件进行合并
            await storage.merge_chunks(source_paths, target_path)
            # 合并成功后将数据插入到数据库
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
            await db.refresh(file_record)
            # 将Redis中的文件上传状态设置为completed
            if source_paths and source_paths[0].parent.exists():
                await asyncio.to_thread(shutil.rmtree, source_paths[0].parent, ignore_errors=True)
            await session_manager.set_status(upload_id, UploadStatus.COMPLETED, file_record_id=file_record.id)

        except Exception as exc:
            await db.rollback()
            await session_manager.set_status(upload_id, UploadStatus.FAILED, error_msg=str(exc))
            raise




if __name__ == "__main__":
    asyncio.run(merge_file("1"))

