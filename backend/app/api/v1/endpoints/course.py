from fastapi import APIRouter, Depends
from app.core.dependencies import get_teacher
from app.models.table import User
from app.services.course_service import CourseService
from app.schemas.course_schema import CourseCreate, CourseResponse


router = APIRouter()


@router.post("/register", response_model=CourseResponse)
async def register_course(
        course_in: CourseCreate,
        teacher: User = Depends(get_teacher),
        course_service: CourseService = Depends()
):
    return await course_service.register_course(course_in, teacher.id)
