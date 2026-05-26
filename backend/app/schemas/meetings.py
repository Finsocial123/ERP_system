from pydantic import BaseModel
from datetime import datetime
from app.models.meeting import MeetingType, MeetingStatus

class MeetingListItemOut(BaseModel):
    id: int
    title: str
    meeting_type: MeetingType
    status: MeetingStatus  
    class_id: int | None
    section_id: int | None
    teacher_id: int | None
    created_by_user_id: int
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    scheduled_at: datetime | None
    record: bool
    recording_url: str | None

    class Config:
        from_attributes: True

class MeetingListOut(BaseModel):
    items: list[MeetingListItemOut]
    total: int


class TeacherClassOut(BaseModel):
    class_id: int
    class_name: str
    section_id: int | None
    section_name: str | None
    subject_id: int
    subject_name: str

    class Config:
        from_attributes = True