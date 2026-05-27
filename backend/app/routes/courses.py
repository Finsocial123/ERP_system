from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.core.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.user import User
from app.models.video_watch_progress import VideoWatchProgress
from app.schemas.course import CourseOut
from app.utils.dependencies import get_current_user, require_role
from app.utils.cloudinary import upload_file, delete_file

router = APIRouter(
    prefix="/courses",
    tags=["Courses"]
)


def build_course_out(course: Course) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "thumbnail_url": course.thumbnail_url,
        "teacher_id": course.teacher_id,
        "teacher_name": course.teacher.name if course.teacher else None,
        "created_at": course.created_at
    }


# Create course
@router.post("/")
def create_course(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    thumbnail_url = None

    if thumbnail:
        result = upload_file(
            thumbnail.file,
            folder="lms/thumbnails",
            resource_type="image"
        )
        thumbnail_url = result["url"]

    course = Course(
        title=title,
        description=description,
        thumbnail_url=thumbnail_url,
        teacher_id=current_user.id
    )

    db.add(course)
    db.commit()
    db.refresh(course)

    return {
        "message": "Course created successfully",
        "course_id": course.id
    }


# Get all courses with optional search
@router.get("/")
def get_all_courses(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Course)

    if search:
        query = query.filter(
            or_(
                Course.title.ilike(f"%{search}%"),
                Course.description.ilike(f"%{search}%")
            )
        )

    courses = query.all()
    return [build_course_out(c) for c in courses]


# Get courses created by the logged-in teacher/admin
@router.get("/my-created")
def get_my_created_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    courses = db.query(Course).filter(
        Course.teacher_id == current_user.id
    ).all()

    return [build_course_out(c) for c in courses]


# Get single course
@router.get("/{course_id}")
def get_course(
    course_id: int,
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return build_course_out(course)


# Update course
@router.put("/{course_id}")
def update_course(
    course_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your course")

    if title:
        course.title = title

    if description is not None:
        course.description = description

    if thumbnail:
        result = upload_file(
            thumbnail.file,
            folder="lms/thumbnails",
            resource_type="image"
        )
        course.thumbnail_url = result["url"]

    db.commit()
    db.refresh(course)

    return {"message": "Course updated successfully"}


# Delete course
@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your course")

    db.delete(course)
    db.commit()

    return {"message": "Course deleted successfully"}


# Get students enrolled in a course with full course-specific progress report (teacher/admin)
def build_student_course_progress_report(course_id: int, db: Session) -> list[dict]:
    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id
    ).order_by(Lesson.order.asc(), Lesson.id.asc()).all()

    lesson_ids = [lesson.id for lesson in lessons]
    total_lessons = len(lessons)

    enrollments = db.query(Enrollment).filter(
        Enrollment.course_id == course_id
    ).order_by(Enrollment.enrolled_at.desc()).all()

    student_ids = [enrollment.student_id for enrollment in enrollments]

    progress_map = {}
    watch_map = {}

    if student_ids and lesson_ids:
        progress_map = {
            (record.student_id, record.lesson_id): record
            for record in db.query(LessonProgress).filter(
                LessonProgress.student_id.in_(student_ids),
                LessonProgress.lesson_id.in_(lesson_ids),
            ).all()
        }

        watch_map = {
            (record.student_id, record.lesson_id): record
            for record in db.query(VideoWatchProgress).filter(
                VideoWatchProgress.student_id.in_(student_ids),
                VideoWatchProgress.lesson_id.in_(lesson_ids),
            ).all()
        }

    result = []

    for enrollment in enrollments:
        student = db.query(User).filter(User.id == enrollment.student_id).first()
        if not student:
            continue

        lesson_reports = []
        completed_lessons = 0

        for lesson in lessons:
            progress_record = progress_map.get((student.id, lesson.id))
            watch_record = watch_map.get((student.id, lesson.id))
            completed = bool(progress_record.completed) if progress_record else False

            if completed:
                completed_lessons += 1

            lesson_reports.append({
                "lesson_id": lesson.id,
                "title": lesson.title,
                "order": lesson.order,
                "completed": completed,
                "completed_at": progress_record.completed_at if progress_record else None,
                "has_video": bool(lesson.video_url or lesson.external_video_link),
                "watched_seconds": round(watch_record.watched_seconds, 2) if watch_record else 0,
                "video_duration_seconds": round(watch_record.video_duration_seconds, 2) if watch_record else 0,
            })

        calculated_progress = (
            round((completed_lessons / total_lessons) * 100, 2)
            if total_lessons > 0
            else round(float(enrollment.progress or 0), 2)
        )

        # Keep the stored enrollment percentage in sync when lessons were added/removed
        # after the student's last completion update.
        if round(float(enrollment.progress or 0), 2) != calculated_progress:
            enrollment.progress = calculated_progress

        result.append({
            "enrollment_id": enrollment.id,
            "student_id": student.id,
            "student_name": student.name,
            "student_email": student.email,
            "progress": calculated_progress,
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "pending_lessons": max(total_lessons - completed_lessons, 0),
            "enrolled_at": enrollment.enrolled_at,
            "lessons": lesson_reports,
        })

    db.commit()

    return result


def ensure_course_report_access(course_id: int, current_user: User, db: Session) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your course")

    return course


@router.get("/{course_id}/students")
def get_enrolled_students(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    ensure_course_report_access(course_id, current_user, db)
    return build_student_course_progress_report(course_id, db)


@router.get("/{course_id}/students/progress")
def get_course_students_progress_report(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    course = ensure_course_report_access(course_id, current_user, db)
    students = build_student_course_progress_report(course_id, db)

    return {
        "course": build_course_out(course),
        "total_students": len(students),
        "average_progress": round(
            sum(student["progress"] for student in students) / len(students), 2
        ) if students else 0,
        "students": students,
    }
