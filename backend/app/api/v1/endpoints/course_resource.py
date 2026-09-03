from fastapi import APIRouter, Depends, Query
from app.schemas.course_resource_schema import CourseResourceCreate, CourseResourceResponse
from app.rbac.dependencies import get_teacher
from app.models.base import User
from app.services.course_resource_service import CourseResourceService
from app.rbac.dependencies import require_perm
from app.rbac.permissions import Permission


router = APIRouter()


@router.post("/register", response_model=CourseResourceResponse)
async def register_course_resource(
        course_resource_in: CourseResourceCreate,
        course_resource_service: CourseResourceService = Depends(),
        teacher: User = Depends(require_perm(Permission.RESOURCE_CREATE))
):
    course_resource = await course_resource_service.register_course_resource(
        course_resource_in,
        teacher.id
    )
    return course_resource


@router.get("/course/{course_id}", response_model=list[CourseResourceResponse])
async def get_resources_by_course(
        course_id: int,
        skip: int = Query(0, ge=0, description="跳过的记录条数"),
        limit: int = Query(20, ge=1, le=100, description="单次查询的最大返回数据数"),
        course_resource_service: CourseResourceService = Depends()
):
    return await course_resource_service.get_resources_by_course(
        course_id,
        skip,
        limit
    )


@router.get("/file/{file_record_id}", response_model=list[CourseResourceResponse])
async def get_resources_by_file(
        file_record_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100)
):

    pass