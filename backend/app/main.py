from pathlib import Path
import logging
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.core.migrations import run_phase4_migrations, run_startup_migrations
from app.core.redis import init_redis, close_redis          # ← NEW
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
    SchoolBranding,
    SchoolClass,
    Section,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    User,
    RefreshToken,
    PendingSchoolRegistration,
    Announcement,
    Complaint,
    InAppNotification,
    InAppNotificationRead,
    SchoolEvent,
)

from app.routes import (
    academic, attendance, reports, auth, dashboard, exams, fees, homework,
    people, schools, library, timetable, notice, communication, curriculum,
    meetings, assignments, chats, courses, enrollments, lessons, progress,
)

# from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.database import get_async_db
from app.services.meeting_service import sync_live_meetings

if settings.RUN_STARTUP_MIGRATIONS:
    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)

app = FastAPI(title="School ERP Phase 9 API", version="9.0.0")

#schedular for meeting
# add it after deploying db to aws cause it needs ipv4 and 
# supbase doens't have that
# scheduler = AsyncIOScheduler()

# @app.on_event("startup")
# async def start_scheduler():
#     scheduler.add_job(
#         sync_live_meetings,
#         "interval",
#         minutes=5,
#     )
#     scheduler.start()

# @app.on_event("shutdown")
# async def stop_scheduler():
#     scheduler.stop()

@app.get("/health", tags=["Health"])
async def health():
    """
    Liveness check for Docker HEALTHCHECK and the AWS ALB target group.
    Intentionally does NOT touch the database or Redis — a slow/degraded
    DB shouldn't cause the ALB to kill and restart a otherwise-healthy
    container. Keep this fast and dependency-free.
    """
    return {"status": "ok"}

@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-ms"] = str(round(duration_ms, 1))

    log_message = "%s %s %.1fms" % (request.method, request.url.path, duration_ms)
    if duration_ms >= settings.API_SLOW_LOG_MS:
        logging.warning("SLOW API %s", log_message)
    else:
        logging.info("API %s", log_message)

    return response

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

# ---------------------------------------------------------------------------
# Redis lifecycle — graceful degradation if Redis is unavailable
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    await init_redis()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await close_redis()


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

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
app.include_router(assignments.router)
app.include_router(chats.router)
app.include_router(courses.router)
app.include_router(enrollments.router)
app.include_router(lessons.router)
app.include_router(progress.router)
