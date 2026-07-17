from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint, Column, Enum
import enum

# 枚举类型
class UserRole(int, enum.Enum):
    STUDENT = 0
    TEACHER = 1
    ADMIN = 2

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# 用户表
class User(SQLModel, table=True):
    __tablename__ = "user"
    id: int | None = Field(default= None, primary_key= True)
    role: UserRole = Field(default= UserRole.STUDENT, sa_column= Column(Enum(UserRole)))
    username: str = Field(index= True, unique= True)
    password_hash: str
    real_name: str
    email: str | None = Field(default= None)
    avatar: str | None = Field(default= None)
    created_at: datetime = Field(default_factory= utc_now)

# 课程表
class Course(SQLModel, table= True):
    __tablename__ = "course"
    id: int | None = Field(default= None, primary_key= True)
    name: str
    course_code: str | None = Field(default=None, unique=True, index=True,description="课程代码")
    teacher_id: int = Field(foreign_key="user.id",description="创建这门课程的教师id")
    overview: str | None = Field(default="暂无简介", description="课程简介")
    created_at: datetime = Field(default_factory= utc_now)


# 选课表
class Enrollment(SQLModel, table= True):
    __tablename__ = "enrollment"
    # 在 Python 中，带有括号但没有逗号的单元素会被解析为该元素本身，而不是元组（Tuple）。
    # 注意要加,（逗号），否则在Python中会被认成单个元素而非元组
    __table_args__ = (UniqueConstraint("student_id", "course_id", name= "uq_student_course"),)
    id: int | None = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="user.id", description="选修该门课程的学生")
    course_id: int = Field(foreign_key="course.id", description="该门课程的id")
    score: float | None = Field(default= None, description="学生该门课程的分数")

# 课程资源表（一位老师可以上传多个课程资源，一个课程资源只对应一位老师）
# （一门课程有多个课程资源，一个课程资源只对应一门课程）
#  (一个课程资源对应一个文件)
class CourseResource(SQLModel, table= True):
    __tablename__ = "course_resource"
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id",description="该资源对应的课程id")
    file_record_id: int = Field(foreign_key="file_record.id",description="该资源对应的文件id")
    uploaded_by: int = Field(foreign_key="user.id",description="上传该资源的老师id")
    file_name: str = Field(description="该文件的原始文件名")
    title: str
    created_at: datetime = Field(default_factory=utc_now)

# 作业表(一门课程有多个作业，一个作业只对应一门课程)
class Assignment(SQLModel, table= True):
    __tablename__ = "assignment"
    id: int | None = Field(default= None, primary_key= True)
    course_id: int = Field(foreign_key= "course.id",description="该作业对应的课程")
    title: str
    description: str
    deadline: datetime = Field(description="该作业的截止日期")
    created_at: datetime = Field(default_factory=utc_now, description="该作业的创建日期")

# 作业附件表
# 一个作业可以有多个附件，一个附件只对应一个作业
# 一个附件对应一个文件
class AssignmentFile(SQLModel, table= True):
    __tablename__ = "assignment_file"
    id: int | None = Field(default= None, primary_key= True)
    assignment_id: int = Field(foreign_key="assignment.id", description="附件所属的作业id")
    file_record_id: int = Field(foreign_key="file_record.id", description="附件对应的文件id")
    file_name: str = Field(description="该文件的原始文件名")
    uploaded_by: int = Field(foreign_key="user.id", description="该文件的上传者")

# 作业提交记录表
# （一个学生可以有多个提交记录，一个提交记录只对应一个学生）
# （一个作业可以有多个提交记录，一个提交记录只对应一门作业）
# （一个提交对应多个文件，一个文件对应一个提交）
class Submission(SQLModel, table= True):
    __tablename__ = "submission"
    id: int | None = Field(default= None, primary_key= True)
    student_id: int = Field(foreign_key= "user.id", description="提交的学生id")
    assignment_id: int = Field(foreign_key= "assignment.id", description="本次提交对应的作业id")
    score: float | None = Field(default= None,description="本次作业的分数")
    submitted_at: datetime = Field(default_factory=utc_now, description="作业提交时间")
    feedback: str | None = Field(default= None, description="批语")
    attempt: int = Field(default= 1, description="表示第几次提交")





# 作业提交对应文件表
class SubmissionFile(SQLModel, table= True):
    __tablename__ = "submission_file"
    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id", description="本次提交的id")
    file_record_id: int = Field(foreign_key="file_record.id", description="本次提交对应的文件之一的id")
    file_name: str = Field(description="该文件的原始文件名")
    uploaded_by: int = Field(foreign_key="user.id", description="该文件的上传者")

# 文件记录表
class FileRecord(SQLModel, table= True):
    __tablename__ = "file_record"
    id: int | None = Field(default= None, primary_key= True)
    file_ext: str | None = Field(default= None, description="该文件的类型")
    mime_type: str | None = Field(default= None,description="该文件的MIME类型")
    storage_type: str = Field(description="该文件的存储方式：本地 / minio")
    storage_key: str = Field(description="该文件的真实路径")
    total_size: int = Field(description="该文件的大小，单位字节")
    file_hash: str = Field(description="该文件的hash值")
    created_at: datetime = Field(default_factory=utc_now)