from pydantic import BaseModel
from datetime import datetime
from app.models.meeting import MeetingType, MeetingStatus

class CreatedByOut(BaseModel):
    id: int
    full_name: str
    role: str

    class Config:
        from_attributes = True


class MeetingListItemOut(BaseModel):
    id: int
    title: str
    meeting_type: MeetingType
    status: MeetingStatus  
    class_id: int | None
    section_id: int | None
    section_name: str | None = None
    teacher_id: int | None
    created_by_user_id: int | None = None
    created_by: CreatedByOut | None 
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    scheduled_at: datetime | None
    record: bool
    recording_url: str | None

    class Config:
        from_attributes = True

class MeetingListOut(BaseModel):
    items: list[MeetingListItemOut]
    total: int


class TeacherClassOut(BaseModel):
    class_id: int
    class_name: str
    section_id: int | None = None  
    section_name: str | None = None
    subject_id: int
    subject_name: str

    class Config:
        from_attributes = True


class TeacherMeetingCreate(BaseModel):
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    title: str


class AdminMeetingCreate(BaseModel):
    title: str


class MeetingCreateOut(BaseModel):
    meeting_id: int
    join_url: str

    class Config:
        from_attributes = True


class TeacherMeetingSchedule(BaseModel):
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    title: str 
    scheduled_at: datetime

class AdminMeetingSchedule(BaseModel):
    title: str
    scheduled_at: datetime
