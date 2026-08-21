from fastapi import APIRouter, Depends
from app.rbac.dependencies import get_teacher, require_perm
from app.rbac.permissions import Permission
from app.models.base import User
from app.services.course_service import CourseService
from app.schemas.course_schema import CourseCreate, CourseResponse


router = APIRouter()


@router.post(
    "/register",
    response_model=CourseResponse,
    summary="教师创建新课程"
)
async def register_course(
        course_in: CourseCreate,
        teacher: User = Depends(require_perm(Permission.COURSE_CREATE)),
        course_service: CourseService = Depends()
):
    return await course_service.register_course(course_in, teacher.id)
