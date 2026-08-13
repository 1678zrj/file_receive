from fastapi import APIRouter, Depends
from app.services.user_service import UserService
from app.schemas.user_schema import UserCreate, UserOut

router = APIRouter()


@router.post("/register", response_model=UserOut)
async def register_user(
        user_in: UserCreate,
        user_service: UserService = Depends()
):
    return await user_service.user_register(user_in)