from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.services.lms_access import ensure_enrollment_for_user_student, get_course_or_404, student_for_user

router = APIRouter(prefix="/enrollments", tags=["LMS Enrollments"])


@router.post("/{course_id}")
def enroll(
    course_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    course = get_course_or_404(db, school_id, course_id)
    enrollment = ensure_enrollment_for_user_student(db, school_id, current_user, course)
    return {"message": f"Enrolled in '{course.title}' successfully", "enrollment_id": enrollment.id}


@router.delete("/{course_id}")
def unenroll(
    course_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    enrollment = db.query(Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == course_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="You are not enrolled in this course")
    course = get_course_or_404(db, school_id, course_id)
    if course.school_id != school_id:
        raise HTTPException(status_code=403, detail="Invalid course")
    db.delete(enrollment)
    db.commit()
    return {"message": "Unenrolled successfully"}


@router.get("/my")
def get_my_enrollments(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    student = student_for_user(db, school_id, current_user)
    if not student:
        return []

    # Auto-create enrollments for every published course assigned to this student's class/section.
    courses = db.query(Course).filter(
        Course.school_id == school_id,
        Course.is_active.is_(True),
        Course.status == "PUBLISHED",
        Course.class_id == student.class_id,
    ).all()
    rows = []
    for course in courses:
        if course.section_id is not None and course.section_id != student.section_id:
            continue
        enrollment = ensure_enrollment_for_user_student(db, school_id, current_user, course)
        rows.append({
            "enrollment_id": enrollment.id,
            "course_id": course.id,
            "course_title": course.title,
            "teacher_name": course.teacher.full_name if course.teacher else None,
            "progress": enrollment.progress,
            "enrolled_at": enrollment.enrolled_at,
        })
    return rows


@router.get("/check/{course_id}")
def check_enrollment(
    course_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.STUDENT.value:
        return {"enrolled": False}
    course = get_course_or_404(db, school_id, course_id)
    try:
        enrollment = ensure_enrollment_for_user_student(db, school_id, current_user, course)
    except HTTPException:
        return {"enrolled": False}
    return {"enrolled": enrollment is not None}
