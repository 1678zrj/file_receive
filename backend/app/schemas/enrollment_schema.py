from pydantic import BaseModel


class EnrollmentCreate(BaseModel):
    course_id: int


class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    score: float | None


class CourseStudentRead(BaseModel):
    student_id: int
    username: str
    real_name: str
    score: float | None