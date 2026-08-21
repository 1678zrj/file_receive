from app.models.base import Enrollment
from collections.abc import Sequence
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlmodel import func
from sqlalchemy.engine import RowMapping
from app.models.base import User, Enrollment

class EnrollmentCrud:

    async def create_enrollment(self, db: AsyncSession, enrollment_data_dict: dict) -> Enrollment:
        enrollment = Enrollment(**enrollment_data_dict)
        db.add(enrollment)
        await db.flush()
        return enrollment


    async def get_course_students(
            self,
            db: AsyncSession,
            course_id: int,
            page: int = 1,
            size: int = 10
    ) -> Sequence[RowMapping]:
        """
            select user.id, user.username, user.real_name, enrollment.score
            from user join enrollment on user.id = enrollment.student_id
            where enrollment.course_id = :course_id
        """
        # 基础连接查询
        base_stmt = (select(
            User.id.label("student_id"),
            User.username,
            User.real_name,
            Enrollment.score
        ).join(Enrollment, User.id == Enrollment.student_id)
        .where(Enrollment.course_id == course_id))

        # 计算offset
        offset = (page - 1) * size
        paged_stmt = base_stmt.offset(offset).limit(size)
        results = await db.exec(paged_stmt)
        return results.mappings().all()

    async def count_students_by_course_id(
            self,
            db: AsyncSession,
            course_id: int
    ) -> int:
        # 查询总数
        count_stmt = (
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.course_id == course_id)
        )
        total = (await db.exec(count_stmt)).one()
        return total



enrollment_crud = EnrollmentCrud()

