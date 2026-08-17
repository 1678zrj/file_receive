from fastapi import APIRouter, Depends, Query
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentResponse, CourseStudentRead
from app.services.enrollment_service import EnrollmentService
from app.rbac.dependencies import get_current_user
from app.models.table import User
from app.schemas.common_schema import PageResponse
from app.rbac.dependencies import require_perm
from app.rbac.permissions import Permission


router = APIRouter()


@router.post("/register", response_model=EnrollmentResponse)
async def enrollment_register(
        enrollment_in: EnrollmentCreate,
        enrollment_service: EnrollmentService = Depends(),
        current_user: User = Depends(require_perm(Permission.COURSE_ENROLL))
):
    enrollment_record = await enrollment_service.register_enrollment(
        enrollment_in,
        current_user.id
    )
    return enrollment_record


# 后续加上分页
@router.post(
    "/{course_id}/students",
    response_model=PageResponse[CourseStudentRead]
)
async def get_course_students(
        course_id: int,
        page: int = Query(default=1, ge=1, description="页码，从1开始"),
        size: int = Query(default=10, ge=1, le=100, description="每页条数，最大100"),
        enrollment_service: EnrollmentService = Depends()
):
    return await enrollment_service.get_course_students(
        course_id,
        page,
        size
    )
