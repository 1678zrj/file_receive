from app.api.v1.endpoints import upload
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])