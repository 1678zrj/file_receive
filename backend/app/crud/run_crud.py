import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.agent import Run
from sqlmodel import select, update
from app.models.agent import RunStatus
from app.models.base import utc_now


class RunCrud:

    async def create_run(self, db: AsyncSession, run_data_dict: dict) -> Run:
        new_run = Run(**run_data_dict)
        db.add(new_run)
        await db.flush()
        return new_run

    async def get_run_by_id(self, db:AsyncSession , id: uuid.UUID) -> Run | None:
        stmt = select(
            Run
        ).where(
            Run.id == id
        )
        result = await db.exec(stmt)
        return result.first()


    async def get_run_by_user_idempotency_key(
            self,
            db: AsyncSession,
            user_id: int,
            idempotency_key: str
    ) -> Run | None:
        stmt = select(
            Run
        ).where(
            Run.user_id == user_id,
            Run.idempotency_key == idempotency_key
        )
        result = await db.exec(stmt)
        return result.first()

    async def get_active_run_by_thread_id(
            self,
            db: AsyncSession,
            thread_id: str,
    ) -> Run | None:
        stmt = select(
            Run
        ).where(
            Run.thread_id == thread_id,
            Run.status.in_(
                [
                    RunStatus.QUEUED.value,
                    RunStatus.IN_PROGRESS.value,
                    RunStatus.REQUIRES_ACTION.value
                ]
            )
        )
        result = await db.exec(stmt)
        return result.first()

    async def update_run_status(self, db: AsyncSession, id: uuid.UUID, src_status: str, dest_status: str):
        stmt = update(Run).where(
            Run.id == id,
            Run.status == src_status
        ).values(
            status = dest_status
        )
        result = await db.exec(stmt)
        return result
    # 这种情况只有in_progress状态到completed
    async def set_run_completed(self, db: AsyncSession, id: uuid.UUID):
        stmt = update(Run).where(
            Run.id == id,
            Run.status == RunStatus.IN_PROGRESS.value
        ).values(
            status = RunStatus.COMPLETED.value,
            finished_at = utc_now()
        )
        await db.exec(stmt)




run_crud = RunCrud()