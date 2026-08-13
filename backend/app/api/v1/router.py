from app.api.v1.endpoints import upload, auth, user, course, course_resource, enrollment
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(user.router, prefix="/user", tags=["User"])
api_router.include_router(course.router, prefix="/course", tags=["Course"])
api_router.include_router(course_resource.router, prefix="/course-resource", tags=["CourseResource"])
api_router.include_router(enrollment.router, prefix="/enrollment", tags=["Enrollment"])