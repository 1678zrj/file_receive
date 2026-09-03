import time

from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends, HTTPException, status
from app.db.session import get_session
from app.auth.jwt import jwt_manager
from app.auth.pwd_hash import pwd_manager
from app.models.base import User
from app.crud.user_crud import user_crud
from app.schemas.auth_schema import Token
from jose import JWTError
from app.redis.cache import CacheService, get_cache_service
from fastapi.concurrency import run_in_threadpool
from app.schemas.user_schema import UserCreate
import asyncio

class UserService:
    def __init__(
            self,
            db: AsyncSession = Depends(get_session),
            cache_service: CacheService = Depends(get_cache_service)
    ):
        self.db = db
        self.cache_service = cache_service

    async def authenticate_user(self, username: str, password: str) -> Token:
        user: User = await user_crud.get_by_username(self.db, username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名错误"
            )
        # CPU密集型操作，放入线程池
        verify_ps = await run_in_threadpool(pwd_manager.verify_password, password, user.password_hash)
        # verify_ps = await asyncio.to_thread(pwd_manager.verify_password, password, user.password_hash)
        # verify_ps = pwd_manager.verify_password(plain_password=password, hashed_password=user.password_hash)
        if not verify_ps:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码错误"
            )
        access_token = jwt_manager.create_access_token(
            # jwt标准里规定sub必须是字符串
            data={"sub": str(user.id), "username": user.username, "role": user.role}
        )
        refresh_token = jwt_manager.create_refresh_token(
            data={"sub": str(user.id), "username": user.username}
        )
        return Token(
            access_token=access_token,
            refresh_token=refresh_token
        )

    async def refresh_token(self, refresh_token: str) -> str:
        # 解码refresh_token
        try:
            data = jwt_manager.decode_token(refresh_token)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token无效: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # 获取其中的数据
        id = data.get("sub")
        # 不存在数据抛出异常
        if id is None:
            raise HTTPException(status_code=401, detail="Token 载荷非法：缺少用户标识")
        token_type = data.get("type")
        # 防止拿access_token冒充refresh_token
        if token_type != "refresh":
            raise HTTPException(status_code=401, detail="Token 类型错误")
        # 数据存在继续校验是否存在于数据库中
        id = int(id)
        user = await user_crud.get_by_id(self.db, id)
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        new_access_token = jwt_manager.create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": user.role}
        )
        return new_access_token

    async def access_token(self, access_token: str) -> User:
        start = time.perf_counter()
        try:
            data = jwt_manager.decode_token(access_token)
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token无效: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        jwt_time = time.perf_counter()
        # 获取其中的数据
        id = data.get("sub")
        # 不存在数据抛出异常
        if id is None:
            raise HTTPException(status_code=401, detail="Token 载荷非法：缺少用户标识")
        token_type = data.get("type")
        # 防止拿access_token冒充refresh_token
        if token_type != "access":
            raise HTTPException(status_code=401, detail="Token 类型错误")
        id = int(id)
        key = f"user:{id}"
        user = await self.cache_service.get(key)
        db_time = time.perf_counter()
        print(
            f"""
        jwt:
        {(jwt_time - start) * 1000:.3f} ms

        db:
        {(db_time - jwt_time) * 1000:.3f} ms

        total:
        {(db_time - start) * 1000:.3f} ms
        """
        )
        if user:
            return User.model_validate_json(user)
        user = await user_crud.get_by_id(self.db, id)
        # db_time = time.perf_counter()

        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在")
        await self.cache_service.set(key, user.model_dump_json())
        return user

    async def user_register(self, user_in: UserCreate) -> User:
        user_exist = await user_crud.get_by_username(self.db, user_in.username)
        if user_exist:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        user_data = user_in.model_dump(exclude_unset=True)
        password = user_data.pop("password")
        password_hash = await asyncio.to_thread(pwd_manager.hash_password,password)
        user_data["password_hash"] = password_hash
        new_user = await user_crud.create_user(self.db, user_data)
        await self.db.commit()
        return new_user