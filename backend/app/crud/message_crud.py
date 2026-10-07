import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models.agent import Message, MessageRole

class MessageCrud:
    async def create_message(self, db: AsyncSession, message_data_dict: dict) -> Message:
        new_message = Message(
            **message_data_dict
        )
        db.add(new_message)
        await db.flush()
        return new_message

    async def get_assistant_message_by_run_id(self, db: AsyncSession, run_id: uuid.UUID) -> Message | None:
        stmt = select(
            Message
        ).where(
            Message.run_id == run_id,
            Message.role == MessageRole.ASSISTANT.value
        )
        result = await db.exec(stmt)
        return result.first()
    async def get_user_message_by_run_id(self, db: AsyncSession, run_id: uuid.UUID)-> Message | None:
        stmt = select(
            Message
        ).where(
            Message.run_id == run_id,
            Message.role == MessageRole.USER.value
        ).order_by(
            Message.created_at.desc()
        )
        result = await db.exec(stmt)
        return result.first()

    async def get_thread_messages(
            self,
            db: AsyncSession,
            thread_id: uuid.UUID
    ) -> list[Message]:
        stmt = select(Message).where(
            Message.thread_id == thread_id
        ).order_by(
            # 时间尺度上，越早的越小
            # 升序排序，越往下时间尺度越大，消息越新
            Message.created_at.asc()
        )
        result = await db.exec(stmt)
        return result.all()


message_crud = MessageCrud()
