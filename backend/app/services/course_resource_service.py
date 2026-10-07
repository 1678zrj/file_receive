from app.crud.course_resource_crud import course_resource_crud
from app.crud.upload_crud import upload_crud
from app.db.session import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends
from app.schemas.course_resource_schema import CourseResourceCreate
from app.models.base import CourseResource, User, UserRole
from fastapi import HTTPException, status
from app.crud.course_crud import course_crud


class CourseResourceService:
    def __init__(
            self,
            db: AsyncSession = Depends(get_session)
    ):
        self.db = db

    async def register_course_resource(
            self,
            course_resource_in: CourseResourceCreate,
            teacher: User
    ) -> CourseResource:
        # 先检测课程是否存在
        course = await course_crud.get_course_by_id(self.db, course_resource_in.course_id)
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"课程ID {course_resource_in.course_id} 不存在"
            )
        # 课程存在，检查上传该课程的老师是否是课程的任课教师
        if course.teacher_id != teacher.id and teacher.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权管理该课程的资源文件"
            )
        # 检查文件是否存在
        file_record = await upload_crud.get_file_record_by_id(self.db, course_resource_in.file_record_id)
        if file_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"课程资源文件{course_resource_in.file_name}不存在"
            )
        course_resource_data = course_resource_in.model_dump()
        course_resource_data["uploaded_by"] = teacher.id
        new_course_resource = await course_resource_crud.create_course_resource(self.db, course_resource_data)
        await self.db.commit()
        return new_course_resource

    async def get_resources_by_course(
            self,
            course_id: int,
            skip: int = 0,
            limit: int = 100
    ) -> list[CourseResource]:
        course_resources = await course_resource_crud.get_course_resource_by_course_id(
            self.db,
            course_id,
            skip,
            limit
        )
        return course_resources

    async def get_resources_by_file(
            self,
            file_record_id: int,
            skip: int = 0,
            limit: int = 0
    ) -> list[CourseResource]:
        course_resources = await course_resource_crud.get_course_resource_by_file_id(
            self.db,
            file_record_id,
            skip,
            limit
        )
        return course_resources
