from datetime import date

from pydantic import BaseModel, Field


class AttendanceEntry(BaseModel):
    student_id: int
    status: str = Field(default="PRESENT", pattern="^(PRESENT|ABSENT|LEAVE|HALF_DAY)$")
    note: str | None = None


class BulkAttendanceCreate(BaseModel):
    session_id: int
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    date: date
    entries: list[AttendanceEntry]


class AttendanceUpdate(BaseModel):
    status: str = Field(pattern="^(PRESENT|ABSENT|LEAVE|HALF_DAY)$")
    note: str | None = None


class AttendanceRead(BaseModel):
    id: int
    student_id: int
    student_name: str | None = None  # Populated for parents viewing children's attendance
    class_id: int
    section_id: int | None = None
    session_id: int
    date: date
    status: str
    note: str | None = None
    marked_by: int | None = None

    model_config = {"from_attributes": True}


class StudentAttendanceSummary(BaseModel):
    student_id: int
    student_name: str
    admission_no: str
    total_days: int
    present: int
    absent: int
    leave: int
    half_day: int
    percentage: float
    low_attendance: bool


class DayAttendanceRecord(BaseModel):
    student_id: int
    student_name: str
    admission_no: str
    roll_number: str | None = None
    status: str | None = None
    note: str | None = None
    attendance_id: int | None = None
