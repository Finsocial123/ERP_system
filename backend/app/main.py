from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.core.migrations import run_phase4_migrations, run_startup_migrations
from app.models import (  # noqa: F401
    AcademicSession,
    ClassTeacherAssignment,
    Department,
    HomeworkAssignment,
    HomeworkSubmission,
    TimetableDay,
    TimetableEntry,
    TimetablePeriod,
    Exam,
    ExamMark,
    ExamSubject,
    FeeAssignment,
    FeeCategory,
    FeeExpense,
    FeePayment,
    FeeStructure,
    StudentFeeRecord,
    ParentGuardian,
    School,
    SchoolClass,
    Section,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    User,
    Announcement,
    Circular,
    Complaint,
    InAppNotification,
    InAppNotificationRead,
    SchoolEvent,
    SupportTicket,
)

from app.routes import academic, attendance, reports,auth, dashboard, exams,fees, homework, people, schools, library, timetable, notice, communication, curriculum, meetings

Base.metadata.create_all(bind=engine)
run_startup_migrations(engine)

app = FastAPI(title="School ERP Phase 9 API", version="9.0.0")

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "School ERP Phase 9 API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(schools.router)
app.include_router(academic.router)
app.include_router(people.router)
app.include_router(dashboard.router)
app.include_router(notice.router)
app.include_router(communication.router)
app.include_router(attendance.router)
app.include_router(homework.router)
app.include_router(timetable.router)
app.include_router(exams.router)
app.include_router(fees.router)
app.include_router(library.router)
app.include_router(reports.router)
app.include_router(curriculum.router)
app.include_router(meetings.router)
