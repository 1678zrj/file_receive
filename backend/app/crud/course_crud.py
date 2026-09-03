from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.base import Course


class CourseCrud:

    async def get_course_by_id(self, db: AsyncSession, id: int) -> Course | None:
        stat = select(Course).where(Course.id == id)
        res = await db.exec(stat)
        return res.first()

    async def get_course_by_code(self, db: AsyncSession, course_code: str) -> Course | None:
        stat = select(Course).where(Course.course_code == course_code)
        res = await db.exec(stat)
        return res.first()

    async def create_course(self, db: AsyncSession, course_data_dict: dict) -> Course:
        new_course = Course(**course_data_dict)
        db.add(new_course)
        await db.flush()
        return new_course


course_crud = CourseCrud()
