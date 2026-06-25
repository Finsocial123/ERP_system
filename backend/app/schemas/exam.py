from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator


class ExamMetaItem(BaseModel):
    id: int
    name: str
    extra: str | None = None


class ExamMetaResponse(BaseModel):
    classes: list[ExamMetaItem]
    sections: list[ExamMetaItem]
    subjects: list[ExamMetaItem]
    teachers: list[ExamMetaItem]
    academic_sessions: list[ExamMetaItem]
    current_academic_session_id: int | None = None


class ExamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    exam_type: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    academic_session_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class ExamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    exam_type: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = None
    academic_session_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    result_status: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class ExamRead(BaseModel):
    id: int
    name: str
    exam_type: str | None = None
    description: str | None = None
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    academic_session_id: int | None = None
    class_name: str | None = None
    academic_session_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    result_status: str
    is_active: bool
    subjects_count: int
    marks_entered_count: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class ExamSubjectCreate(BaseModel):
    subject_id: int
    teacher_id: int | None = None
    max_marks: float = Field(default=100, gt=0)
    pass_marks: float = Field(default=33, ge=0)
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(default=None, max_length=120)
    timetable_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_marks_and_time(self):
        if self.pass_marks > self.max_marks:
            raise ValueError("Pass marks cannot be greater than max marks")
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class ExamSubjectUpdate(BaseModel):
    subject_id: int | None = None
    teacher_id: int | None = None
    max_marks: float | None = Field(default=None, gt=0)
    pass_marks: float | None = Field(default=None, ge=0)
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(default=None, max_length=120)
    timetable_note: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_time(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class ExamSubjectRead(BaseModel):
    id: int
    exam_id: int
    subject_id: int
    teacher_id: int | None = None
    subject_name: str | None = None
    teacher_name: str | None = None
    max_marks: float
    pass_marks: float
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = None
    timetable_note: str | None = None
    is_active: bool
    marks_entered_count: int
    created_at: datetime
    updated_at: datetime


class ExamTimetableItem(BaseModel):
    exam_id: int
    exam_name: str
    exam_type: str | None = None
    result_status: str
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    class_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    exam_subject_id: int
    subject_id: int
    subject_name: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    max_marks: float
    pass_marks: float
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = None
    timetable_note: str | None = None
    schedule_source: str = "MANUAL"
    student_id: int | None = None
    student_name: str | None = None
    admission_no: str | None = None
    roll_number: str | None = None


class ExamStudentRead(BaseModel):
    id: int
    admission_no: str
    roll_number: str | None = None
    student_name: str
    class_name: str | None = None
    section_name: str | None = None


class ExamMarkPayload(BaseModel):
    student_id: int
    marks_obtained: float | None = Field(default=None, ge=0)
    is_absent: bool = False
    remarks: str | None = Field(default=None, max_length=1000)


class ExamBulkMarksPayload(BaseModel):
    exam_subject_id: int
    marks: list[ExamMarkPayload]


class ExamMarkRead(BaseModel):
    id: int | None = None
    exam_subject_id: int
    student_id: int
    student_name: str
    admission_no: str
    roll_number: str | None = None
    marks_obtained: float | None = None
    max_marks: float
    pass_marks: float
    grade: str | None = None
    is_absent: bool
    pass_status: str
    remarks: str | None = None
    updated_at: datetime | None = None


class ExamSubjectResultRead(BaseModel):
    exam: ExamRead
    exam_subject: ExamSubjectRead
    results: list[ExamMarkRead]
    summary: dict[str, float | int | str]


class ReportCardSubject(BaseModel):
    exam_subject_id: int
    subject_id: int
    subject_name: str
    max_marks: float
    pass_marks: float
    marks_obtained: float | None = None
    grade: str | None = None
    is_absent: bool
    pass_status: str
    remarks: str | None = None


class StudentReportCard(BaseModel):
    exam_id: int
    exam_name: str
    exam_type: str | None = None
    result_status: str
    student_id: int
    student_name: str
    admission_no: str
    roll_number: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    subjects: list[ReportCardSubject]
    total_marks: float
    marks_obtained: float
    percentage: float
    grade: str
    pass_status: str
    published_at: datetime | None = None


class ClassResultResponse(BaseModel):
    exam: ExamRead
    results: list[StudentReportCard]
    summary: dict[str, float | int | str]


class ParentReportCard(StudentReportCard):
    pass
