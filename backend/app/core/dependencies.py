from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi import status

from app.services.user_service import UserService
from app.models.table import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        user_service: UserService = Depends()
) -> User:
    user = await user_service.access_token(access_token=token)
    return user


async def get_teacher(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role < UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要教师或管理员权限"
        )
    return current_user


async def get_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role < UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要管理员权限"
        )
    return current_user
