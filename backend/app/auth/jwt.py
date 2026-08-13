import time

from app.core.config import settings
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
from jose import jwt


class JWTManager:

    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire = timedelta(settings.access_token_expire_minutes)
        self.refresh_token_expire = timedelta(settings.refresh_token_expire_days)

    def _create_access_token(
            self,
            data: dict[str, Any],
            token_type: str,
            expires_delta: timedelta
    ) -> str:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        to_encode.update(
            {
                "exp": expire,
                "iat": now,
                "jti": str(uuid.uuid4()),  # 唯一标识，可用于黑名单
                "type": token_type
            }
        )
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_access_token(
            self,
            data: dict[str, Any],
            expires_delta: timedelta | None = None
    ) -> str:
        delta = expires_delta or self.access_token_expire
        return self._create_access_token(
            data=data,
            token_type="access",
            expires_delta=delta
        )

    def create_refresh_token(
            self,
            data: dict[str, Any],
            expires_delta: timedelta | None = None
    ) -> str:
        delta = expires_delta or self.refresh_token_expire
        return self._create_access_token(
            data=data,
            token_type="refresh",
            expires_delta=delta
        )

    def decode_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])


jwt_manager = JWTManager()


if __name__ == "__main__":
    user_payload = {"sub": "123", "role": 1}

    # 调用的形式完全一致，极其优雅
    start = time.time()
    for i in range(10000):
        access_token = jwt_manager.create_access_token(data=user_payload)
        refresh_token = jwt_manager.create_refresh_token(data=user_payload)  # Refresh Token 通常只需存 sub
        jwt_manager.decode_token(refresh_token)
    end = time.time()
    print(f"耗时：{end - start}s")