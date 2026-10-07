import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.agent import Interrupt, InterruptStatus
from sqlmodel import select

class InterruptCrud:

    async def create_interrupt(self, db: AsyncSession, interrupt_dict: dict) -> Interrupt:
        new_interrupt = Interrupt(**interrupt_dict)
        db.add(new_interrupt)
        return new_interrupt

    async def get_pending_interrupt(
            self,
            db: AsyncSession,
            thread_id: uuid.UUID,
            run_id: uuid.UUID
    ) -> Interrupt | None:
        stmt = select(Interrupt).where(
            Interrupt.thread_id == thread_id,
            Interrupt.run_id == run_id,
            Interrupt.status == InterruptStatus.PENDING.value
        )
        result = await db.exec(stmt)
        return result.first()

    async def update_interrupt_status(self, db: AsyncSession, ):

        pass


interrupt_crud = InterruptCrud()