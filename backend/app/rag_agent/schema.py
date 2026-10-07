from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

class UserRole(int, Enum):
    STUDENT = 0
    TEACHER = 1
    ADMIN = 2


class ToolAction(str, Enum):
    READ = "read"
    WRITE = "write"
    INTERACTIVE = "interactive"


# 中断策略
class InterruptPolicy(str, Enum):
    # 触发中断审核
    REQUIRE_APPROVAL = "require_approval"
    # 触发中断交互
    REQUIRE_INPUT = "require_input"


class ToolMetadata(BaseModel):
    allowed_roles: list[UserRole] = Field(
        default_factory=lambda: [UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN]
    )
    tool_action: ToolAction = ToolAction.READ
    interrupt_policy: InterruptPolicy | None = None
    require_interrupt: bool = False



