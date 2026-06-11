from datetime import date
from pydantic import BaseModel


class AttendanceReportRow(BaseModel):
    student_id: int
    student_name: str
    admission_no: str
    roll_number: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    total_days: int
    present: int
    absent: int
    leave: int
    half_day: int
    percentage: float
    low_attendance: bool


class AttendanceReportResponse(BaseModel):
    session_id: int
    session_name: str
    class_id: int | None = None
    class_name: str | None = None
    section_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    total_students: int
    avg_percentage: float
    low_attendance_count: int
    rows: list[AttendanceReportRow]


class HomeworkReportRow(BaseModel):
    assignment_id: int
    title: str
    subject_name: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    due_date: date
    teacher_name: str | None = None
    total_students: int
    submitted: int
    checked: int
    pending: int
    submission_rate: float


class HomeworkReportResponse(BaseModel):
    session_id: int | None = None
    session_name: str | None = None
    class_id: int | None = None
    rows: list[HomeworkReportRow]


class TeacherReportRow(BaseModel):
    teacher_id: int
    employee_id: str
    full_name: str
    photo_url: str | None = None
    department_name: str | None = None
    email: str | None = None
    phone: str | None = None
    qualification: str | None = None
    joining_date: str | None = None
    status: str
    subjects_assigned: int
    classes_assigned: int


class TeacherReportResponse(BaseModel):
    total_teachers: int
    active_teachers: int
    department_breakdown: list[dict]
    rows: list[TeacherReportRow]


class StudentReportRow(BaseModel):
    student_id: int
    admission_no: str
    roll_number: str | None = None
    full_name: str
    gender: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    admission_date: str | None = None
    status: str


class StudentReportResponse(BaseModel):
    total_students: int
    active_students: int
    class_breakdown: list[dict]
    rows: list[StudentReportRow]


class ReportsOverview(BaseModel):
    total_students: int
    active_students: int
    total_teachers: int
    active_teachers: int
    total_classes: int
    total_exams: int
    published_exams: int
    total_homework: int
    avg_attendance_pct: float
    low_attendance_students: int
    library_books: int
    library_issued: int
    overdue_books: int
