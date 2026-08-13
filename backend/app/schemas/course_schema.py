from pydantic import BaseModel
from datetime import datetime

class CourseCreate(BaseModel):
    # id, created_at为系统级属性，数据库自动生成
    name: str
    course_code: str | None = None
    # 请求体不应该带有teacher_id，id应该从token中获取，防止老师替其它老师创建课程
    # teacher_id: int
    overview: str = "暂无简介"


class CourseResponse(BaseModel):
    id: int
    name: str
    course_code: str | None
    teacher_id: int
    overview: str
    created_at: datetime