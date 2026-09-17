import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update
from app.models.agent import Thread, ThreadStatus


class ThreadCrud:

    async def get_thread_by_id(
            self,
            db: AsyncSession,
            id: uuid.UUID
    ) -> Thread | None:
        stmt = select(Thread).where(
            Thread.id == id
        )
        result = await db.exec(stmt)
        return result.first()

    async def get_user_all_threads(
            self,
            db: AsyncSession,
            user_id: int
    ) -> list[Thread]:
        stmt = select(
            Thread
        ).where(
            Thread.user_id == user_id
        ).order_by(
            Thread.updated_at.desc()
        )
        result = await db.exec(stmt)
        return result.all()

    async def get_user_active_threads(
            self,
            db: AsyncSession,
            user_id: int
    ) -> list[Thread]:
        stmt = select(
            Thread
        ).where(
            Thread.user_id == user_id,
            Thread.status == ThreadStatus.ACTIVE.value
        ).order_by(
            Thread.updated_at.desc()
        )
        result = await db.exec(stmt)
        return result.all()

    async def mark_thread_deleted(
            self,
            db: AsyncSession,
            thread_id: uuid.UUID
    ):
        stmt = update(
            Thread
        ).where(
            Thread.id == thread_id
        ).values(
            status = ThreadStatus.DELETED.value
        )
        result = await db.exec(stmt)
        return result



thread_crud = ThreadCrud()