from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.table import CourseResource
from sqlmodel import select

class CourseResourceCrud:

    async def create_course_resource(self, db: AsyncSession, course_resource_data: dict) -> CourseResource:
        course_resource = CourseResource(**course_resource_data)
        db.add(course_resource)
        await db.flush()
        return course_resource

    async def get_course_resource_by_course_id(
            self,
            db: AsyncSession,
            course_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> list[CourseResource]:
        stat = (
            select(CourseResource)
            .where(CourseResource.course_id == course_id)
            .order_by(CourseResource.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        results = await db.exec(stat)
        return results.all()


    async def get_course_resource_by_file_id(
            self,
            db: AsyncSession,
            file_record_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> list[CourseResource]:
        stat = (
            select(CourseResource)
            .where(CourseResource.file_record_id==file_record_id)
            .order_by(CourseResource.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        results = await db.exec(stat)
        return results.all()


course_resource_crud = CourseResourceCrud()
