from fastapi import APIRouter, Depends, Response, Cookie, HTTPException
from app.schemas.auth_schema import Token, AccessToken
from app.services.user_service import UserService
from app.schemas.auth_schema import UserLogin
from app.core.config import settings
from app.models.base import User
from app.rbac.dependencies import get_current_user

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
        response: Response,
        user_login: UserLogin,
        user_service: UserService = Depends()
):
    token = await user_service.authenticate_user(
        username=user_login.username,
        password=user_login.password
    )
    response.set_cookie(
        key="refresh_token",
        value=token.refresh_token,
        httponly=True,  # 禁止 JS 读取， 防止XSS
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        expires=settings.refresh_token_expire_days * 24 * 60 * 60,
        samesite="lax",
        secure=False  # 开发环境设为 False
    )
    return token


@router.post("/refresh")
async def refresh_token(
        refresh_token: str | None = Cookie(default=None),
        user_service: UserService = Depends()
):
    if refresh_token is None:
        raise HTTPException(
            status_code=401,
            detail="未提供刷新令牌"
        )
    new_access_token = await user_service.refresh_token(refresh_token)
    return AccessToken(
        access_token=new_access_token
    )


@router.get("/me", response_model=User)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user
