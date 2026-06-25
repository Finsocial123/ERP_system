from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.services.lms_access import course_matches_student, ensure_enrollment_for_user_student, get_course_or_404, student_for_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
router = APIRouter(prefix='/enrollments', tags=['LMS Enrollments'])

@router.post('/{course_id}')
async def enroll(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.STUDENT)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    enrollment = await ensure_enrollment_for_user_student(db, school_id, current_user, course)
    return {'message': f"Enrolled in '{course.title}' successfully", 'enrollment_id': enrollment.id}

@router.delete('/{course_id}')
async def unenroll(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.STUDENT)), db: AsyncSession=Depends(get_async_db)):
    enrollment = await async_query(db, Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == course_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail='You are not enrolled in this course')
    course = await get_course_or_404(db, school_id, course_id)
    if course.school_id != school_id:
        raise HTTPException(status_code=403, detail='Invalid course')
    await db.delete(enrollment)
    await db.commit()
    return {'message': 'Unenrolled successfully'}

@router.get('/my')
async def get_my_enrollments(school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.STUDENT)), db: AsyncSession=Depends(get_async_db)):
    student = await student_for_user(db, school_id, current_user)
    if not student:
        return []
    courses = await async_query(db, Course).filter(Course.school_id == school_id, Course.is_active.is_(True), Course.status == 'PUBLISHED', Course.class_id == student.class_id).all()
    rows = []
    for course in courses:
        if not course_matches_student(course, student):
            continue
        enrollment = await ensure_enrollment_for_user_student(db, school_id, current_user, course)
        rows.append({'enrollment_id': enrollment.id, 'course_id': course.id, 'course_title': course.title, 'teacher_name': course.teacher.full_name if course.teacher else None, 'progress': enrollment.progress, 'enrolled_at': enrollment.enrolled_at})
    return rows

@router.get('/check/{course_id}')
async def check_enrollment(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.STUDENT.value:
        return {'enrolled': False}
    course = await get_course_or_404(db, school_id, course_id)
    try:
        enrollment = await ensure_enrollment_for_user_student(db, school_id, current_user, course)
    except HTTPException:
        return {'enrolled': False}
    return {'enrolled': enrollment is not None}
