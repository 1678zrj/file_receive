from pydantic import BaseModel
from datetime import datetime


class CourseResourceCreate(BaseModel):
    # id, created_at是系统级属性，交给数据库生成
    course_id: int
    file_record_id: int
    # uploaded_by可以从token中获取，不需要
    file_name: str
    title: str


class CourseResourceResponse(BaseModel):
    id: int
    course_id: int
    file_record_id: int
    uploaded_by: int
    file_name: str
    title: str
    created_at: datetime

