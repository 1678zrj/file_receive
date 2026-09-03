import shutil
import uuid

import aiofiles.os

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
from pathlib import Path
from sqlalchemy.exc import IntegrityError

class FileHashMismatchError(Exception):
    """分片合并后的实际 Hash 与上传会话声明的 Hash 不一致。"""

    pass

async def cleanup_resources(
    files: list[Path | str] | None = None,
    dirs: list[Path | str] | None = None,
):
    """统一在后台线程中清理临时文件与目录，自动忽略不存在及权限异常"""
    def _sync_clean():
        if files:
            for file_path in files:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
        if dirs:
            for dir_path in dirs:
                try:
                    shutil.rmtree(dir_path, ignore_errors=True)
                except Exception:
                    pass

    await asyncio.to_thread(_sync_clean)





@broker.task(task_name="merge_file_task")
async def merge_file(
    upload_id: str
):
    """当前文档还是以绝对路径存储在数据库中，未来需要修改"""
    storage = LocalStorage()
    redis = RedisManager.get_client()
    session_manager = SessionManager(redis_client=redis)
    lock_key = f"lock:upload:merge:{upload_id}"
    # 使用分布式锁保证并发安全,后续引入看门狗机制,防止合并期间锁过期
    async with redis.lock(lock_key, timeout=600):
        # 合并任务改造
        session = await session_manager.get_session(upload_id)
        # 幂等校验,通常另一个重复请求拿到锁后,就已经是完成或者失败了
        if session.status in (UploadStatus.FAILED, UploadStatus.COMPLETED):
            return
        total_chunks = session.total_chunks
        source_paths = [build_tmp_path(upload_id, i) for i in range(total_chunks)]
        chunks_dir = source_paths[0].parent
        true_target_path = build_final_path(upload_id, session.file_name)
        fake_target_path = Path(f"{true_target_path}.{uuid.uuid4().hex}.tmp")
        # 数据库永远保证兜底校验
        # 1 合并前秒传检测: 若已有记录,直接复用并清理分片
        async with AsyncSessionLocal() as db:
            existing_file_record = await upload_crud.get_file_record_by_hash(db, session.file_hash)
            # 说明已经合并完成了,worker可能重复执行
            if existing_file_record is not None:
                await session_manager.set_completed(upload_id, existing_file_record.id)
                # 此时只有分片,对分片进行清理
                await cleanup_resources(dirs=[chunks_dir])
                return
        # 2 状态标记(用于精准的失败资源回滚)
        # 临时合并文件是否存在
        temp_merged = False
        # 最终文件是否存在且属于本次任务
        target_merged = False
        try:
            # 将文件进行合并
            actual_hash = await storage.merge_chunks(source_paths, fake_target_path)
            # 临时合并文件此时存在
            temp_merged = True
            # 合并得到的文件的hash值与客户端传来的不符
            if actual_hash.lower() != session.file_hash.lower():
                raise FileHashMismatchError(f"Hash mismatch. Expected: {session.file_hash}, Actual: {actual_hash}")
            # 进行到这里说明合并成功且hash值一致,可以进行原子落盘,
            await aiofiles.os.replace(fake_target_path, true_target_path)
            # 临时合并文件此时不存在,最终文件存在
            temp_merged = False
            target_merged = True
            # 以上操作完成后,可以进行数据库持久化保存了
            async with AsyncSessionLocal() as db:
                try:
                    # 合并成功后将数据插入到数据库
                    file_record = await upload_crud.create_upload(
                        db=db,
                        storage_type=settings.storage_type,
                        storage_key=str(true_target_path),
                        total_size=session.total_size,
                        file_hash=session.file_hash,
                        file_ext=session.file_ext,
                        mime_type=session.mime_type
                    )
                    await db.commit()
                    await db.refresh(file_record)
                    # 运行到这里说明成功落盘了
                    target_merged = False
                    # 先后有讲究,因为运行到这里已经实际落库落盘了,不能进行清理
                    # 所以要防止redis保存影响状态更新
                    await session_manager.set_completed(upload_id, file_record.id)
                # 该异常说明已经有另一个用户传了相同文件并落库了
                except IntegrityError:
                    await db.rollback()
                    # 文件记录已存在的话可以设置状态为completed
                    existing_file_record = await upload_crud.get_file_record_by_hash(db, actual_hash)
                    # 记录已存在可以直接结束,不必抛出异常
                    if existing_file_record is not None:
                        await session_manager.set_completed(upload_id, existing_file_record.id)
                        # 如果已有其它用户上传文件落盘了
                        if existing_file_record.storage_key != str(true_target_path):
                            # 当前用户的需要清理
                            await cleanup_resources(files=[true_target_path])
                            # 清理完成了才设置为False
                            target_merged = False
                        # 落盘的就是当前用户上传的文件,可能是worker重复执行了
                        else:
                            # 最终文件当然不能删除
                            target_merged = False
                    else:
                        raise
            # 成功完成,清理分片目录
            await cleanup_resources(dirs=[chunks_dir])
        except Exception as e:
            # 统一异常处理: 设置失败 收集残留文件并清理
            await session_manager.set_failed(upload_id, error_msg=str(e))
            clean_files = []
            if temp_merged:
                clean_files.append(fake_target_path)
            if target_merged:
                clean_files.append(true_target_path)
            await cleanup_resources(files=clean_files, dirs=[chunks_dir])
            raise







if __name__ == "__main__":
    asyncio.run(merge_file("1"))

