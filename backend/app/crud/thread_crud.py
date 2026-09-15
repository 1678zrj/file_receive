import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models.agent import Thread


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



thread_crud = ThreadCrud()