from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends
from app.db.session import get_session
from app.models.base import Course
from app.schemas.course_schema import CourseCreate
from app.crud.user_crud import user_crud
from app.crud.course_crud import course_crud
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

class CourseService:
    def __init__(
            self,
            db: AsyncSession = Depends(get_session)
    ):
        self.db = db

    async def register_course(self, course_in: CourseCreate, teacher_id: int) -> Course:
        if course_in.course_code:
            existing = await course_crud.get_course_by_code(self.db, course_in.course_code)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"课程代码 '{course_in.course_code}' 已存在"
                )
        course_data = course_in.model_dump(exclude_unset=True)
        course_data["teacher_id"] = teacher_id
        try:
            new_course = await course_crud.create_course(self.db, course_data)
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            # 识别是否是唯一约束性冲突
            if "Duplicate entry" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="课程编号或其他唯一标识已存在，请勿重复创建"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数据完整性校验失败"
            )
        return new_course
