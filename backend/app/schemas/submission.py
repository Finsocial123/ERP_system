from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubmissionOut(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    assignment_id: int
    file_url: Optional[str] = None
    grade: Optional[float] = None
    feedback: Optional[str] = None
    submitted_at: datetime

    class Config:
        from_attributes = True


class GradeSubmission(BaseModel):
    grade: float       # 0.0 - 100.0
    feedback: Optional[str] = None