from enum import Enum
from typing import Set, Dict
from app.models.table import UserRole


class Permission(str, Enum):
    # 课程管理
    COURSE_CREATE = "course:create"
    COURSE_UPDATE = "course:update"
    COURSE_DELETE = "course:delete"
    # 课程资源管理
    RESOURCE_CREATE = "resource:create"
    RESOURCE_DELETE = "resource:delete"
    # 课程作业管理
    ASSIGNMENT_CREATE = "assignment:create"
    ASSIGNMENT_UPDATE = "assignment:update"
    ASSIGNMENT_DELETE = "assignment:delete"
    ASSIGNMENT_GRADE = "assignment:grade"

    # 选课 作业提交
    COURSE_ENROLL = "course:enroll"
    SUBMISSION_CREATE = "submission:create"


ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: set(Permission),
    UserRole.TEACHER: {
        Permission.COURSE_CREATE,
        Permission.COURSE_UPDATE,
        Permission.COURSE_DELETE,
        Permission.RESOURCE_CREATE,
        Permission.RESOURCE_DELETE,
        Permission.ASSIGNMENT_CREATE,
        Permission.ASSIGNMENT_UPDATE,
        Permission.ASSIGNMENT_DELETE,
        Permission.ASSIGNMENT_GRADE
    },
    UserRole.STUDENT: {
        Permission.COURSE_ENROLL,
        Permission.SUBMISSION_CREATE
    }
}
