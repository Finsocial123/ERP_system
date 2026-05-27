from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None


class AssignmentOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    course_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class QuizRequest(BaseModel):
    num_questions: int = 5
    difficulty: Literal["easy", "medium", "hard"] = "medium"