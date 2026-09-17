import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from app.crud.thread_crud import thread_crud
from app.models.agent import Thread, ThreadStatus
from app.db.session import get_session
from fastapi import Depends, HTTPException, status


class ThreadService:
    def __init__(
            self,
            db: AsyncSession
    ):
        self.db = db

    # 给出用户当前活跃状态的会话
    async def list_threads(
            self,
            user_id: int
    ) -> list[Thread]:
        user_threads = await thread_crud.get_user_active_threads(
            self.db,
            user_id
        )
        return user_threads

    async def delete_thread(
            self,
            thread_id: uuid.UUID,
            user_id: int
    ):
        existing_thread = await thread_crud.get_thread_by_id(
            self.db,
            thread_id
        )
        if existing_thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )
        if existing_thread.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无权删除改会话"
            )
        if existing_thread.status != ThreadStatus.ACTIVE.value:
            return
        result = await thread_crud.mark_thread_deleted(
            self.db,
            thread_id
        )
        await self.db.commit()
        return result



async def get_thread_service(
    db: AsyncSession = Depends(get_session)
):
    return ThreadService(
        db = db
    )


