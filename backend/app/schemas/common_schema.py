from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    total: int  # 总记录数
    page: int  # 当前页码
    size: int  # 每页条数
    items: list[T]
