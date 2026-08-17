from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi import status

from app.models.table import User
from app.services.user_service import UserService
from app.models.table import User, UserRole
from app.rbac.permissions import Permission, ROLE_PERMISSIONS

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

# 这里被解码的是元组
def require_perm(*required_perms: Permission):
    """
        粗粒度鉴权,传入的参数是需要的权限,
        为了给依赖函数传参,故通过闭包机制返回真正被依赖的函数对象
    """
    async def checker(current_user: User = Depends(get_current_user)):
        # 如果当前用户是管理员,那直接通过
        if current_user.role == UserRole.ADMIN:
            return current_user

        # 先获取当前用户拥有的权限
        cur_user_pers = ROLE_PERMISSIONS.get(current_user.role, set())
        # 检测当前用户拥有的权限是否符合当前操作需要的权限之一
        # 传入的参数是元组,因此需要先转化为集合
        if not (set(required_perms) & cur_user_pers):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：需要以下权限之一 {[p.value for p in required_perms]}"
            )
        return current_user



    return checker











