from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enrollment import Enrollment
from app.models.course import Course
from app.models.user import User
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(
    prefix="/enrollments",
    tags=["Enrollments"]
)


# Student enrolls in a course
@router.post("/{course_id}")
def enroll(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    existing = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == course_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Already enrolled in this course"
        )

    enrollment = Enrollment(
        student_id=current_user.id,
        course_id=course_id
    )

    db.add(enrollment)
    db.commit()

    return {"message": f"Enrolled in '{course.title}' successfully"}


# Student unenrolls from a course
@router.delete("/{course_id}")
def unenroll(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == course_id
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=404,
            detail="You are not enrolled in this course"
        )

    db.delete(enrollment)
    db.commit()

    return {"message": "Unenrolled successfully"}


# Student gets their enrolled courses
@router.get("/my")
def get_my_enrollments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id
    ).all()

    result = []
    for enr in enrollments:
        course = db.query(Course).filter(
            Course.id == enr.course_id
        ).first()

        teacher = db.query(User).filter(
            User.id == course.teacher_id
        ).first() if course else None

        result.append({
            "enrollment_id": enr.id,
            "course_id": enr.course_id,
            "course_title": course.title if course else None,
            "teacher_name": teacher.name if teacher else None,
            "progress": enr.progress,
            "enrolled_at": enr.enrolled_at
        })

    return result


# Check if student is enrolled in a specific course
@router.get("/check/{course_id}")
def check_enrollment(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == course_id
    ).first()

    return {"enrolled": enrollment is not None}