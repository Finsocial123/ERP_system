from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EnrollmentOut(BaseModel):
    id: int
    student_id: int
    course_id: int
    course_title: Optional[str] = None
    teacher_name: Optional[str] = None
    progress: float
    enrolled_at: datetime

    class Config:
        from_attributes = True