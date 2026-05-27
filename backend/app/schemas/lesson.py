from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LessonCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order: Optional[int] = 0
    external_video_link: Optional[str] = None


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    external_video_link: Optional[str] = None


class LessonOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    order: int
    video_url: Optional[str] = None
    pdf_url: Optional[str] = None
    external_video_link: Optional[str] = None
    course_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SummaryRequest(BaseModel):
    source: str | None = None
    