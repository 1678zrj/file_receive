from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import get_session
from fastapi import Depends
from app.schemas.enrollment_schema import EnrollmentCreate, CourseStudentRead
from app.models.table import Enrollment
from app.crud.course_crud import course_crud
from app.crud.enrollement_crud import enrollment_crud
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from pydantic import TypeAdapter
from app.schemas.common_schema import PageResponse


class EnrollmentService:

    def __init__(self, db: AsyncSession = Depends(get_session)):
        self.db = db

    async def register_enrollment(
            self,
            enrollment_in: EnrollmentCreate,
            student_id: int
    ) -> Enrollment:
        existing = await course_crud.get_course_by_id(self.db, enrollment_in.course_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"课程ID {enrollment_in.course_id} 不存在"
            )
        enrollment_data = enrollment_in.model_dump()
        enrollment_data["student_id"] = student_id
        try:
            new_enrollment = await enrollment_crud.create_enrollment(self.db, enrollment_data)
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            # 方式 1：检查通用或特定数据库错误码（以 PyMySQL/MySQLdb 为例，错误码 1062 代表重复键）
            orig_error = getattr(e, "orig", None)
            # pymysql 的 orig.args[0] 通常是错误码
            if orig_error and hasattr(orig_error, "args") and orig_error.args[0] == 1062:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="您已选过该课程，请勿重复选课"
                )

            # 方式 2：如果在该接口下 IntegrityError 绝大多数情况都是唯一键冲突，可以直接返回 409
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="选课冲突或已被选过"
            )
        return new_enrollment

    async def get_course_students(
            self,
            course_id: int,
            page: int = 1,
            size: int = 10
    ) -> PageResponse[CourseStudentRead]:
        total = await enrollment_crud.count_students_by_course_id(self.db, course_id)
        results = await enrollment_crud.get_course_students(self.db, course_id, page, size)
        adapter = TypeAdapter(list[CourseStudentRead])
        students = adapter.dump_python(results)
        # students = [CourseStudentRead.model_validate(result) for result in results]
        return PageResponse(
            total=total,
            page=page,
            size=size,
            items=students
        )
