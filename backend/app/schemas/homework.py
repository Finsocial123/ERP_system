from datetime import date, datetime

from pydantic import BaseModel, Field


class HomeworkMetaItem(BaseModel):
    id: int
    name: str
    extra: str | None = None


class HomeworkMetaResponse(BaseModel):
    classes: list[HomeworkMetaItem]
    sections: list[HomeworkMetaItem]
    subjects: list[HomeworkMetaItem]
    teachers: list[HomeworkMetaItem]
    current_academic_session_id: int | None = None


class HomeworkStats(BaseModel):
    total_students: int
    pending: int
    submitted: int
    checked: int


class HomeworkAssignmentRead(BaseModel):
    id: int
    title: str
    description: str | None = None
    due_date: date
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    subject_id: int | None = None
    teacher_id: int | None = None
    academic_session_id: int | None = None
    class_name: str | None = None
    subject_name: str | None = None
    teacher_name: str | None = None
    attachment_url: str | None = None
    attachment_filename: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stats: HomeworkStats


class StudentHomeworkRead(HomeworkAssignmentRead):
    submission_id: int | None = None
    submission_status: str
    submitted_at: datetime | None = None
    answer_text: str | None = None
    submission_attachment_url: str | None = None
    submission_attachment_filename: str | None = None
    teacher_feedback: str | None = None
    checked_at: datetime | None = None


class ParentHomeworkRead(StudentHomeworkRead):
    student_id: int
    student_name: str
    admission_no: str


class HomeworkSubmissionRead(BaseModel):
    id: int | None = None
    homework_id: int
    student_id: int
    student_name: str
    admission_no: str
    roll_number: str | None = None
    status: str
    answer_text: str | None = None
    attachment_url: str | None = None
    attachment_filename: str | None = None
    teacher_feedback: str | None = None
    submitted_at: datetime | None = None
    checked_at: datetime | None = None


class HomeworkCheckPayload(BaseModel):
    teacher_feedback: str | None = Field(default=None, max_length=2000)
