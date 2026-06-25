from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    class_id: int
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    status: str = "PUBLISHED"


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    class_id: Optional[int] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    subject_id: Optional[int] = None
    teacher_id: Optional[int] = None
    status: Optional[str] = None


class CourseMetaItem(BaseModel):
    id: int
    name: str
    extra: Optional[str] = None


class CourseMetaResponse(BaseModel):
    classes: list[CourseMetaItem]
    sections: list[CourseMetaItem]
    subjects: list[CourseMetaItem]
    teachers: list[CourseMetaItem]
    current_academic_session_id: Optional[int] = None


class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    school_id: Optional[int] = None
    class_id: Optional[int] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    subject_id: Optional[int] = None
    academic_session_id: Optional[int] = None
    teacher_id: int
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    subject_name: Optional[str] = None
    academic_session_name: Optional[str] = None
    status: str = "PUBLISHED"
    is_active: bool = True
    lessons_count: int = 0
    enrolled_students_count: int = 0
    progress: Optional[float] = None
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    admission_no: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
