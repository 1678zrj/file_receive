import uuid
from app.crud.message_crud import message_crud
from app.crud.thread_crud import thread_crud
from app.models.agent import Message, ThreadStatus
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from fastapi import Depends
from fastapi import HTTPException, status

class MessageService:
    def __init__(
            self,
            db: AsyncSession
    ):
        self.db = db

    async def get_thread_messages(
            self,
            thread_id: uuid.UUID,
            user_id: int
    ) -> list[Message]:
        existing_thread = await thread_crud.get_thread_by_id(
            self.db,
            thread_id
        )
        if existing_thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread不存在"
            )
        if existing_thread.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无权访问该会话"
            )
        if existing_thread.status != ThreadStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该会话已过期"
            )
        thread_messages = await message_crud.get_thread_messages(
            self.db,
            thread_id
        )
        return thread_messages


async def get_message_service(
    db: AsyncSession = Depends(get_session)
):
    return MessageService(
        db = db
    )


