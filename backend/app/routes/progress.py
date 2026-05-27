from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.user import User
from app.models.video_watch_progress import VideoWatchProgress
from app.utils.dependencies import require_role

router = APIRouter(
    prefix="/progress",
    tags=["Progress"]
)

# A 10 minute video needs about 7.5 minutes of real credited watch time.
VIDEO_COMPLETION_RATIO = 0.75

# Client sends small pings. Backend caps each ping so a skipped video cannot be completed
# by sending one large fake delta.
MAX_CREDIT_PER_PING_SECONDS = 20.0
SERVER_CLOCK_GRACE_SECONDS = 3.0


class VideoWatchPayload(BaseModel):
    watched_seconds_delta: float = Field(default=0, ge=0, le=120)
    video_duration_seconds: Optional[float] = Field(default=None, ge=0)
    current_position_seconds: Optional[float] = Field(default=None, ge=0)


def get_required_watch_seconds(video_duration_seconds: Optional[float]) -> float:
    if not video_duration_seconds or video_duration_seconds <= 0:
        return 0.0
    return round(video_duration_seconds * VIDEO_COMPLETION_RATIO, 2)


def get_watch_status(record: Optional[VideoWatchProgress]) -> dict:
    watched_seconds = round(record.watched_seconds, 2) if record else 0.0
    duration_seconds = round(record.video_duration_seconds, 2) if record else 0.0
    required_seconds = get_required_watch_seconds(duration_seconds)

    return {
        "watched_seconds": watched_seconds,
        "video_duration_seconds": duration_seconds,
        "required_watch_seconds": required_seconds,
        "watch_percentage": round(
            min((watched_seconds / required_seconds) * 100, 100), 2
        ) if required_seconds > 0 else 0,
        "can_mark_complete": required_seconds > 0 and watched_seconds >= required_seconds,
    }


def get_lesson_or_404(lesson_id: int, db: Session) -> Lesson:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    return lesson


def ensure_student_enrolled(student_id: int, course_id: int, db: Session) -> Enrollment:
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=403,
            detail="You are not enrolled in this course"
        )

    return enrollment


def recalculate_course_progress(
    student_id: int,
    course_id: int,
    db: Session
):
    """Recalculate and update the enrollment progress % for a student in a course."""
    total_lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id
    ).count()

    if total_lessons == 0:
        return

    completed = db.query(LessonProgress).join(
        Lesson, LessonProgress.lesson_id == Lesson.id
    ).filter(
        LessonProgress.student_id == student_id,
        Lesson.course_id == course_id,
        LessonProgress.completed == True
    ).count()

    percentage = round((completed / total_lessons) * 100, 2)

    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id
    ).first()

    if enrollment:
        enrollment.progress = percentage
        db.commit()


@router.get("/{lesson_id}/watch")
def get_video_watch_progress(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    lesson = get_lesson_or_404(lesson_id, db)
    ensure_student_enrolled(current_user.id, lesson.course_id, db)

    record = db.query(VideoWatchProgress).filter(
        VideoWatchProgress.student_id == current_user.id,
        VideoWatchProgress.lesson_id == lesson_id
    ).first()

    return get_watch_status(record)


@router.post("/{lesson_id}/watch")
def track_video_watch_progress(
    lesson_id: int,
    payload: VideoWatchPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    lesson = get_lesson_or_404(lesson_id, db)
    ensure_student_enrolled(current_user.id, lesson.course_id, db)

    if not lesson.video_url and not lesson.external_video_link:
        return {
            "watched_seconds": 0,
            "video_duration_seconds": 0,
            "required_watch_seconds": 0,
            "watch_percentage": 0,
            "can_mark_complete": True,
        }

    record = db.query(VideoWatchProgress).filter(
        VideoWatchProgress.student_id == current_user.id,
        VideoWatchProgress.lesson_id == lesson_id
    ).first()

    if not record:
        record = VideoWatchProgress(
            student_id=current_user.id,
            lesson_id=lesson_id,
            watched_seconds=0,
            video_duration_seconds=0,
            max_position_seconds=0,
            last_position_seconds=0,
        )
        db.add(record)
        db.flush()

    if payload.video_duration_seconds and payload.video_duration_seconds > 0:
        record.video_duration_seconds = max(
            record.video_duration_seconds or 0,
            float(payload.video_duration_seconds)
        )

    if payload.current_position_seconds is not None:
        current_position = max(float(payload.current_position_seconds), 0)
        record.last_position_seconds = current_position
        record.max_position_seconds = max(
            record.max_position_seconds or 0,
            current_position
        )

    now = datetime.now(timezone.utc)
    requested_delta = max(float(payload.watched_seconds_delta or 0), 0)

    if record.last_watch_ping_at:
        last_ping_at = record.last_watch_ping_at
        if last_ping_at.tzinfo is None:
            last_ping_at = last_ping_at.replace(tzinfo=timezone.utc)

        elapsed_since_last_ping = max(
            (now - last_ping_at).total_seconds(),
            0
        )
        server_allowed_delta = elapsed_since_last_ping + SERVER_CLOCK_GRACE_SECONDS
    else:
        # First ping gets a small grace so the frontend can batch its initial seconds.
        server_allowed_delta = MAX_CREDIT_PER_PING_SECONDS

    credited_delta = min(
        requested_delta,
        server_allowed_delta,
        MAX_CREDIT_PER_PING_SECONDS
    )

    if credited_delta > 0:
        next_watched_seconds = (record.watched_seconds or 0) + credited_delta

        # Do not let watched time go beyond the known duration.
        if record.video_duration_seconds and record.video_duration_seconds > 0:
            next_watched_seconds = min(
                next_watched_seconds,
                record.video_duration_seconds
            )

        record.watched_seconds = round(next_watched_seconds, 2)

    record.last_watch_ping_at = now

    db.commit()
    db.refresh(record)

    return get_watch_status(record)


# Mark a lesson as complete
@router.post("/{lesson_id}/complete")
def mark_lesson_complete(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    lesson = get_lesson_or_404(lesson_id, db)

    # check student is enrolled
    ensure_student_enrolled(current_user.id, lesson.course_id, db)

    # Uploaded video lessons require real credited watch time before completion.
    # External embeds are not forced unless watch data exists, because browsers cannot
    # reliably read third-party player duration without provider-specific APIs.
    should_enforce_video_watch = bool(lesson.video_url)

    if should_enforce_video_watch:
        watch_record = db.query(VideoWatchProgress).filter(
            VideoWatchProgress.student_id == current_user.id,
            VideoWatchProgress.lesson_id == lesson_id
        ).first()

        watch_status = get_watch_status(watch_record)

        if watch_status["video_duration_seconds"] <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please start playing the video first so its duration can be detected."
            )

        if not watch_status["can_mark_complete"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You are required to watch at least 75% of this video "
                    "before marking the lesson complete."
                )
            )

    # check if already marked
    existing = db.query(LessonProgress).filter(
        LessonProgress.student_id == current_user.id,
        LessonProgress.lesson_id == lesson_id
    ).first()

    if existing:
        if existing.completed:
            return {"message": "Lesson already marked as complete"}
        existing.completed = True
        existing.completed_at = datetime.now(timezone.utc)
    else:
        progress = LessonProgress(
            student_id=current_user.id,
            lesson_id=lesson_id,
            completed=True,
            completed_at=datetime.now(timezone.utc)
        )
        db.add(progress)

    db.commit()

    # update enrollment progress %
    recalculate_course_progress(
        current_user.id,
        lesson.course_id,
        db
    )

    return {"message": "Lesson marked as complete"}


# Mark a lesson as incomplete (undo)
@router.delete("/{lesson_id}/complete")
def mark_lesson_incomplete(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    lesson = get_lesson_or_404(lesson_id, db)

    record = db.query(LessonProgress).filter(
        LessonProgress.student_id == current_user.id,
        LessonProgress.lesson_id == lesson_id
    ).first()

    if not record:
        raise HTTPException(
            status_code=404,
            detail="No progress record found"
        )

    record.completed = False
    record.completed_at = None
    db.commit()

    recalculate_course_progress(
        current_user.id,
        lesson.course_id,
        db
    )

    return {"message": "Lesson marked as incomplete"}


# Get progress for a student in a course
@router.get("/course/{course_id}")
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    enrollment = ensure_student_enrolled(current_user.id, course_id, db)

    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id
    ).order_by(Lesson.order).all()

    lesson_ids = [lesson.id for lesson in lessons]

    progress_records = {}
    watch_records = {}

    if lesson_ids:
        progress_records = {
            record.lesson_id: record
            for record in db.query(LessonProgress).filter(
                LessonProgress.student_id == current_user.id,
                LessonProgress.lesson_id.in_(lesson_ids)
            ).all()
        }

        watch_records = {
            record.lesson_id: record
            for record in db.query(VideoWatchProgress).filter(
                VideoWatchProgress.student_id == current_user.id,
                VideoWatchProgress.lesson_id.in_(lesson_ids)
            ).all()
        }

    lesson_statuses = []
    for lesson in lessons:
        record = progress_records.get(lesson.id)
        watch_record = watch_records.get(lesson.id)
        watch_status = get_watch_status(watch_record)
        has_trackable_video = bool(lesson.video_url)
        completed = record.completed if record else False

        lesson_statuses.append({
            "lesson_id": lesson.id,
            "title": lesson.title,
            "order": lesson.order,
            "completed": completed,
            "completed_at": record.completed_at if record else None,
            "has_video": bool(lesson.video_url or lesson.external_video_link),
            "has_trackable_video": has_trackable_video,
            "watched_seconds": watch_status["watched_seconds"],
            "video_duration_seconds": watch_status["video_duration_seconds"],
            "required_watch_seconds": watch_status["required_watch_seconds"],
            "watch_percentage": watch_status["watch_percentage"],
            "can_mark_complete": (
                completed or
                not has_trackable_video or
                watch_status["can_mark_complete"]
            ),
        })

    return {
        "course_id": course_id,
        "overall_progress": enrollment.progress,
        "total_lessons": len(lessons),
        "completed_lessons": sum(
            1 for l in lesson_statuses if l["completed"]
        ),
        "lessons": lesson_statuses
    }
