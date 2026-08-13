from datetime import datetime

from pydantic import BaseModel
from app.models.table import UserRole


class UserCreate(BaseModel):
    # id和created_at属于系统字段，靠数据库自动生成
    # role是有默认值的字段，且不能为空
    role: UserRole = UserRole.STUDENT
    # 该字段是必填字段
    username: str
    # 该字段是必填字段
    password: str
    # 该字段是必填字段
    real_name: str
    # 该字段是可选字段
    email: str | None = None
    # 该字段是可选字段
    avatar: str | None = None

class UserOut(BaseModel):
    id: int
    role: UserRole
    username: str
    real_name: str
    email: str | None
    avatar: str | None
    created_at: datetime
