from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Subject
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.people import Student, Teacher, TeacherSubject
from app.models.progress import LessonProgress
from app.models.user import User, UserRole
from app.models.video_watch_progress import VideoWatchProgress
from app.schemas.common import MessageResponse
from app.schemas.course import CourseMetaItem, CourseMetaResponse, CourseOut
from app.dependencies.academic_session import selected_academic_session
from app.services.lms_access import ALL_LMS_ROLES, ADMIN_ROLES, MANAGER_ROLES, can_manage_course, children_for_parent, ensure_can_manage_course, ensure_can_view_course, ensure_enrollment_for_user_student, full_student_name, get_course_or_404, course_matches_student, student_for_user, teacher_for_user, teacher_has_scope, validate_course_scope, validate_same_school
from app.utils.cloudinary import upload_file
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
from app.core.sections import class_section_options, validate_class_section_name
from app.services.notification_service import notify_student_scope
router = APIRouter(prefix='/courses', tags=['LMS Courses'])
COURSE_STATUSES = {'DRAFT', 'PUBLISHED', 'ARCHIVED'}

def _safe_status(value: str | None) -> str:
    status_value = (value or 'PUBLISHED').strip().upper()
    if status_value not in COURSE_STATUSES:
        raise HTTPException(status_code=400, detail='Course status must be DRAFT, PUBLISHED, or ARCHIVED')
    return status_value

async def _teacher_name(db: AsyncSession, school_id: int, teacher_user_id: int | None, teacher_user: User | None=None) -> str | None:
    """Resolve the displayed course teacher name without lazy-loading Course.teacher."""
    if teacher_user_id is None and teacher_user is None:
        return None
    if teacher_user_id is not None:
        teacher = await async_query(db, Teacher).filter(
            Teacher.school_id == school_id,
            Teacher.user_id == teacher_user_id,
            Teacher.is_active.is_(True),
        ).order_by(Teacher.id.desc()).first()
        if teacher:
            return teacher.full_name
    if teacher_user:
        return teacher_user.full_name
    if teacher_user_id is not None:
        user = await async_query(db, User).filter(User.id == teacher_user_id).first()
        return user.full_name if user else None
    return None

async def _related_item(db: AsyncSession, course: Course, attr_name: str, model, item_id: int | None):
    """Return a related object without triggering SQLAlchemy async lazy loading."""
    loaded = course.__dict__.get(attr_name)
    if loaded is not None or item_id is None:
        return loaded
    query = async_query(db, model).filter(model.id == item_id)
    if getattr(model, "school_id", None) is not None and course.school_id is not None:
        query = query.filter(model.school_id == course.school_id)
    return await query.first()

async def _course_payload(db: AsyncSession, course: Course, progress: float | None=None, student: Student | None=None) -> CourseOut:
    lessons_count = await async_query(db, Lesson).filter(Lesson.course_id == course.id).count()
    enrolled_count = await async_query(db, Enrollment).filter(Enrollment.course_id == course.id).count()

    school_class = await _related_item(db, course, "school_class", SchoolClass, course.class_id)
    subject = await _related_item(db, course, "subject", Subject, course.subject_id)
    academic_session = await _related_item(db, course, "academic_session", AcademicSession, course.academic_session_id)
    teacher_user = course.__dict__.get("teacher")

    return CourseOut(
        id=course.id,
        title=course.title,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        school_id=course.school_id,
        class_id=course.class_id,
        section_id=course.section_id,
        subject_id=course.subject_id,
        academic_session_id=course.academic_session_id,
        teacher_id=course.teacher_id,
        teacher_name=await _teacher_name(db, course.school_id or 0, course.teacher_id, teacher_user),
        class_name=school_class.name if school_class else None,
        section_name=course.section_name,
        subject_name=subject.name if subject else None,
        academic_session_name=academic_session.name if academic_session else None,
        status=course.status or 'PUBLISHED',
        is_active=bool(course.is_active),
        lessons_count=lessons_count,
        enrolled_students_count=enrolled_count,
        progress=progress,
        student_id=student.id if student else None,
        student_name=full_student_name(student) if student else None,
        admission_no=student.admission_no if student else None,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )

def _base_course_query(db: AsyncSession, school_id: int):
    return async_query(db, Course).options(joinedload(Course.teacher), joinedload(Course.school_class), joinedload(Course.subject), joinedload(Course.academic_session)).filter(Course.school_id == school_id, Course.is_active.is_(True))

async def _teacher_allowed_query(db: AsyncSession, school_id: int, user: User):
    teacher = await teacher_for_user(db, school_id, user)
    query = _base_course_query(db, school_id).filter(Course.teacher_id == user.id)
    if not teacher:
        return query
    scoped_course_ids: set[int] = {course.id for course in await query.all()}
    for course in await _base_course_query(db, school_id).all():
        if course.class_id and await teacher_has_scope(db, school_id, teacher, course.class_id, course.section_id, course.subject_id, course.section_name):
            scoped_course_ids.add(course.id)
    return _base_course_query(db, school_id).filter(Course.id.in_(scoped_course_ids or {-1}))

async def _student_course_rows(db: AsyncSession, school_id: int, user: User) -> list[CourseOut]:
    student = await student_for_user(db, school_id, user)
    if not student or not student.class_id:
        return []

    courses = [course for course in await _base_course_query(db, school_id).filter(Course.status == 'PUBLISHED').order_by(Course.created_at.desc()).all() if course_matches_student(course, student)]
    rows: list[CourseOut] = []
    for course in courses:
        enrollment = await ensure_enrollment_for_user_student(db, school_id, user, course)
        rows.append(await _course_payload(db, course, progress=float(enrollment.progress or 0), student=student))

    return rows

async def _parent_course_rows(db: AsyncSession, school_id: int, user: User) -> list[CourseOut]:
    rows: list[CourseOut] = []
    for child in await children_for_parent(db, school_id, user):
        if not child.user_id or not child.class_id:
            continue
        courses = [course for course in await _base_course_query(db, school_id).filter(Course.status == 'PUBLISHED').order_by(Course.created_at.desc()).all() if course_matches_student(course, child)]
        for course in courses:
            enrollment = await async_query(db, Enrollment).filter(Enrollment.student_id == child.user_id, Enrollment.course_id == course.id).first()
            progress = float(enrollment.progress or 0) if enrollment else 0
            rows.append(await _course_payload(db, course, progress=progress, student=child))
    return rows


async def _teacher_for_course_meta(
    db: AsyncSession,
    school_id: int,
    user: User,
    session_id: int | None,
) -> Teacher | None:
    if session_id is not None:
        teacher = await async_query(db, Teacher).filter(
            Teacher.school_id == school_id,
            Teacher.user_id == user.id,
            Teacher.academic_session_id == session_id,
            Teacher.is_active.is_(True),
        ).first()
        if teacher:
            return teacher
    return await teacher_for_user(db, school_id, user)


def _teacher_meta_items(teachers: list[Teacher]) -> list[CourseMetaItem]:
    """Return LMS teacher choices keyed by login user id without duplicates."""
    seen_user_ids: set[int] = set()
    items: list[CourseMetaItem] = []
    for teacher in teachers:
        if teacher.user_id is None:
            continue
        user_id = int(teacher.user_id)
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        items.append(CourseMetaItem(id=user_id, name=teacher.full_name, extra=teacher.employee_id))
    return items


@router.get('/meta', response_model=CourseMetaResponse)
async def courses_meta(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request=request, current_user=current_user)
    session_id = session.id if session else None

    class_query = async_query(db, SchoolClass).filter(
        SchoolClass.school_id == school_id,
        SchoolClass.is_active.is_(True),
    )
    subject_query = async_query(db, Subject).filter(
        Subject.school_id == school_id,
        Subject.is_active.is_(True),
    )

    if session_id is not None:
        class_query = class_query.filter(SchoolClass.academic_session_id == session_id)
        subject_query = subject_query.filter(Subject.academic_session_id == session_id)

    if current_user.role == UserRole.TEACHER.value:
        teacher = await _teacher_for_course_meta(db, school_id, current_user, session_id)
        if teacher:
            teacher_subjects_query = async_query(db, TeacherSubject).filter_by(
                school_id=school_id,
                teacher_id=teacher.id,
            )
            if session_id is not None:
                teacher_subjects_query = teacher_subjects_query.filter(TeacherSubject.academic_session_id == session_id)
            teacher_subjects = await teacher_subjects_query.all()
            class_ids = {item.class_id for item in teacher_subjects if item.class_id is not None}
            subject_ids = {item.subject_id for item in teacher_subjects if item.subject_id is not None}
            if class_ids:
                class_query = class_query.filter(SchoolClass.id.in_(class_ids))
                subject_query = subject_query.filter(Subject.class_id.in_(class_ids))
            if subject_ids:
                subject_query = subject_query.filter(Subject.id.in_(subject_ids))

    teacher_query = async_query(db, Teacher).filter(
        Teacher.school_id == school_id,
        Teacher.is_active.is_(True),
        Teacher.user_id.isnot(None),
    )
    if session_id is not None:
        teacher_query = teacher_query.filter(Teacher.academic_session_id == session_id)
    teachers = await teacher_query.order_by(Teacher.full_name.asc(), Teacher.id.asc()).all()

    return CourseMetaResponse(
        classes=[CourseMetaItem(id=item.id, name=item.name, extra=item.code) for item in await class_query.order_by(SchoolClass.name.asc()).all()],
        sections=[CourseMetaItem(id=item.id, name=item.name, extra=str(item.extra)) for item in await class_section_options(db, school_id, session_id=session_id)],
        subjects=[CourseMetaItem(id=item.id, name=item.name, extra=str(item.class_id) if item.class_id else None) for item in await subject_query.order_by(Subject.name.asc()).all()],
        teachers=_teacher_meta_items(teachers),
        current_academic_session_id=session_id,
    )

@router.get('/student/my', response_model=list[CourseOut])
async def list_my_student_courses(school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.STUDENT)), db: AsyncSession=Depends(get_async_db)):
    return await _student_course_rows(db, school_id, current_user)

@router.get('/parent/children', response_model=list[CourseOut])
async def list_parent_child_courses(school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.PARENT)), db: AsyncSession=Depends(get_async_db)):
    return await _parent_course_rows(db, school_id, current_user)

@router.get('/', response_model=list[CourseOut])
async def get_all_courses(search: Optional[str]=Query(None), class_id: Optional[int]=Query(None), section_id: Optional[int]=Query(None), subject_id: Optional[int]=Query(None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    if current_user.role == UserRole.TEACHER.value:
        query = await _teacher_allowed_query(db, school_id, current_user)
    else:
        query = _base_course_query(db, school_id)
    if search:
        like = f'%{search.strip()}%'
        query = query.filter(or_(Course.title.ilike(like), Course.description.ilike(like)))
    if class_id is not None:
        query = query.filter(Course.class_id == class_id)
    if section_id is not None:
        if class_id is None:
            query = query.filter(Course.section_id == section_id)
        else:
            section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id)
            query = query.filter(Course.section_name == section_name)
    if subject_id is not None:
        query = query.filter(Course.subject_id == subject_id)
    courses = await query.order_by(Course.created_at.desc()).all()
    return [await _course_payload(db, course) for course in courses]

@router.get('/my-created', response_model=list[CourseOut])
async def get_my_created_courses(school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    courses = await _base_course_query(db, school_id).filter(Course.teacher_id == current_user.id).order_by(Course.created_at.desc()).all()
    return [await _course_payload(db, course) for course in courses]

@router.post('/', response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(title: str=Form(..., min_length=2, max_length=255), description: Optional[str]=Form(None), class_id: int=Form(...), section_id: Optional[int]=Form(None), section_name: Optional[str]=Form(None), subject_id: Optional[int]=Form(None), teacher_id: Optional[int]=Form(None), status_value: str=Form('PUBLISHED', alias='status'), thumbnail: Optional[UploadFile]=File(None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    _, resolved_section_name, _ = await validate_course_scope(db, school_id, class_id, section_id, subject_id, section_name=section_name)
    assigned_teacher_user_id = current_user.id
    if current_user.role == UserRole.TEACHER.value:
        teacher = await teacher_for_user(db, school_id, current_user)
        if not teacher:
            raise HTTPException(status_code=403, detail='Teacher profile not found for this login')
        if not await teacher_has_scope(db, school_id, teacher, class_id, section_id, subject_id, resolved_section_name):
            raise HTTPException(status_code=403, detail='Teacher is not assigned to this class/section/subject')
    elif teacher_id is not None:
        teacher_user = await async_query(db, User).filter(User.id == teacher_id, User.school_id == school_id, User.role == UserRole.TEACHER.value).first()
        if not teacher_user:
            raise HTTPException(status_code=404, detail='Selected teacher user not found for this school')
        assigned_teacher_user_id = teacher_user.id
    thumbnail_url = None
    if thumbnail and thumbnail.filename:
        result = upload_file(thumbnail.file, folder='lms/thumbnails', resource_type='image')
        thumbnail_url = result['url']
    course = Course(school_id=school_id, class_id=class_id, section_id=None, section_name=resolved_section_name, subject_id=subject_id, academic_session_id=None, title=title.strip(), description=description.strip() if description else None, thumbnail_url=thumbnail_url, teacher_id=assigned_teacher_user_id, status=_safe_status(status_value), is_active=True)
    db.add(course)
    await db.flush()
    if course.status == 'PUBLISHED':
        await notify_student_scope(
            db,
            school_id=school_id,
            class_id=course.class_id,
            section_id=course.section_id,
            academic_session_id=None,
            title='New course available',
            message=f"{course.title} is now available in LMS courses.",
            category='COURSE',
            priority='NORMAL',
            created_by=current_user.id,
            student_link='/student-courses',
            parent_link='/parent-courses',
        )
    await db.commit()
    await db.refresh(course)
    return await _course_payload(db, course)

@router.get('/{course_id}', response_model=CourseOut)
async def get_course(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALL_LMS_ROLES)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_view_course(db, school_id, current_user, course)
    progress = None
    student = None
    if current_user.role == UserRole.STUDENT.value:
        student = await student_for_user(db, school_id, current_user)
        enrollment = await async_query(db, Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == course.id).first()
        progress = float(enrollment.progress or 0) if enrollment else 0
    return await _course_payload(db, course, progress=progress, student=student)

@router.put('/{course_id}', response_model=CourseOut)
async def update_course(course_id: int, title: Optional[str]=Form(None), description: Optional[str]=Form(None), class_id: Optional[int]=Form(None), section_id: Optional[int]=Form(None), section_name: Optional[str]=Form(None), subject_id: Optional[int]=Form(None), teacher_id: Optional[int]=Form(None), status_value: Optional[str]=Form(None, alias='status'), thumbnail: Optional[UploadFile]=File(None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)
    next_class_id = class_id if class_id is not None else course.class_id
    next_section_id = section_id if section_id is not None else course.section_id
    next_subject_id = subject_id if subject_id is not None else course.subject_id
    next_section_name = section_name if section_name is not None else course.section_name
    if next_class_id is None:
        raise HTTPException(status_code=400, detail='Class is required')
    _, resolved_section_name, _ = await validate_course_scope(db, school_id, next_class_id, next_section_id, next_subject_id, section_name=next_section_name)
    if current_user.role == UserRole.TEACHER.value:
        teacher = await teacher_for_user(db, school_id, current_user)
        if not teacher or not await teacher_has_scope(db, school_id, teacher, next_class_id, next_section_id, next_subject_id, resolved_section_name):
            raise HTTPException(status_code=403, detail='Teacher is not assigned to this class/section/subject')
    elif teacher_id is not None:
        teacher_user = await async_query(db, User).filter(User.id == teacher_id, User.school_id == school_id, User.role == UserRole.TEACHER.value).first()
        if not teacher_user:
            raise HTTPException(status_code=404, detail='Selected teacher user not found for this school')
        course.teacher_id = teacher_user.id
    if title is not None:
        course.title = title.strip()
    if description is not None:
        course.description = description.strip() if description else None
    course.class_id = next_class_id
    course.section_id = None
    course.section_name = resolved_section_name
    course.subject_id = next_subject_id
    previous_status = course.status
    if status_value is not None:
        course.status = _safe_status(status_value)
    if thumbnail and thumbnail.filename:
        result = upload_file(thumbnail.file, folder='lms/thumbnails', resource_type='image')
        course.thumbnail_url = result['url']
    if course.status == 'PUBLISHED':
        await notify_student_scope(
            db,
            school_id=school_id,
            class_id=course.class_id,
            section_id=course.section_id,
            academic_session_id=None,
            title='Course updated' if previous_status == 'PUBLISHED' else 'New course available',
            message=f"{course.title} has been updated in LMS courses.",
            category='COURSE',
            priority='NORMAL',
            created_by=current_user.id,
            student_link='/student-courses',
            parent_link='/parent-courses',
        )
    await db.commit()
    await db.refresh(course)
    return await _course_payload(db, course)

@router.delete('/{course_id}', response_model=MessageResponse)
async def delete_course(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)
    course.is_active = False
    course.status = 'ARCHIVED'
    await db.commit()
    return {'message': 'Course archived successfully'}

@router.post('/{course_id}/sync-enrollments', response_model=MessageResponse)
async def sync_course_enrollments(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)
    if not course.class_id:
        raise HTTPException(status_code=400, detail='Course class is missing')
    query = async_query(db, Student).filter(Student.school_id == school_id, Student.class_id == course.class_id, Student.is_active.is_(True), Student.user_id.isnot(None))
    if course.section_name:
        query = query.filter(Student.section_name == course.section_name)
    elif course.section_id is not None:
        query = query.filter(Student.section_id == course.section_id)
    created = 0
    for student in await query.all():
        existing = await async_query(db, Enrollment).filter(Enrollment.student_id == student.user_id, Enrollment.course_id == course.id).first()
        if not existing:
            db.add(Enrollment(student_id=student.user_id, course_id=course.id, progress=0))
            created += 1
    await db.commit()
    return {'message': f'Enrollment sync complete. Created {created} new enrollment(s).'}

async def build_student_course_progress_report(course_id: int, school_id: int, db: AsyncSession) -> list[dict]:
    """Build a course progress report with bulk queries.

    This avoids one query per student/lesson and keeps the report fast even when
    a class has many students and lessons.
    """
    lessons = await async_query(db, Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.order.asc(), Lesson.id.asc()).all()
    lesson_ids = [lesson.id for lesson in lessons]
    total_lessons = len(lessons)
    enrollments = await async_query(db, Enrollment).filter(Enrollment.course_id == course_id).order_by(Enrollment.enrolled_at.asc()).all()
    student_user_ids = [enrollment.student_id for enrollment in enrollments]
    if not student_user_ids:
        return []
    users = {user.id: user for user in await async_query(db, User).filter(User.id.in_(student_user_ids)).all()}
    students = {student.user_id: student for student in await async_query(db, Student).filter(Student.school_id == school_id, Student.user_id.in_(student_user_ids)).all() if student.user_id is not None}
    progress_map = {}
    watch_map = {}
    if lesson_ids:
        progress_map = {(record.student_id, record.lesson_id): record for record in await async_query(db, LessonProgress).filter(LessonProgress.student_id.in_(student_user_ids), LessonProgress.lesson_id.in_(lesson_ids)).all()}
        watch_map = {(record.student_id, record.lesson_id): record for record in await async_query(db, VideoWatchProgress).filter(VideoWatchProgress.student_id.in_(student_user_ids), VideoWatchProgress.lesson_id.in_(lesson_ids)).all()}
    result = []
    for enrollment in enrollments:
        user = users.get(enrollment.student_id)
        student = students.get(enrollment.student_id)
        if not user:
            continue
        lesson_reports = []
        completed_lessons = 0
        last_activity_at = None
        for lesson in lessons:
            progress_record = progress_map.get((user.id, lesson.id))
            watch_record = watch_map.get((user.id, lesson.id))
            completed = bool(progress_record.completed) if progress_record else False
            if completed:
                completed_lessons += 1
                if progress_record.completed_at and (last_activity_at is None or progress_record.completed_at > last_activity_at):
                    last_activity_at = progress_record.completed_at
            watched_seconds = round(float(watch_record.watched_seconds or 0), 2) if watch_record else 0
            video_duration_seconds = round(float(watch_record.video_duration_seconds or 0), 2) if watch_record else 0
            watch_percentage = round(min(watched_seconds / video_duration_seconds * 100, 100), 2) if video_duration_seconds else 0
            lesson_reports.append({'lesson_id': lesson.id, 'title': lesson.title, 'order': lesson.order, 'completed': completed, 'completed_at': progress_record.completed_at if progress_record else None, 'has_video': bool(lesson.video_url or lesson.external_video_link), 'watched_seconds': watched_seconds, 'video_duration_seconds': video_duration_seconds, 'watch_percentage': watch_percentage})
        calculated_progress = round(completed_lessons / total_lessons * 100, 2) if total_lessons else 0
        if round(float(enrollment.progress or 0), 2) != calculated_progress:
            enrollment.progress = calculated_progress
        if total_lessons == 0:
            status_label = 'NO_LESSONS'
        elif calculated_progress >= 100:
            status_label = 'COMPLETED'
        elif calculated_progress > 0:
            status_label = 'IN_PROGRESS'
        else:
            status_label = 'NOT_STARTED'
        result.append({'enrollment_id': enrollment.id, 'student_user_id': user.id, 'student_id': student.id if student else None, 'student_name': full_student_name(student) if student else user.full_name, 'student_email': user.email, 'admission_no': student.admission_no if student else None, 'roll_number': student.roll_number if student else None, 'progress': calculated_progress, 'status': status_label, 'total_lessons': total_lessons, 'completed_lessons': completed_lessons, 'pending_lessons': max(total_lessons - completed_lessons, 0), 'enrolled_at': enrollment.enrolled_at, 'last_activity_at': last_activity_at, 'lessons': lesson_reports})
    await db.commit()
    return sorted(result, key=lambda item: (item.get('roll_number') or '', (item.get('student_name') or '').lower()))

@router.get('/{course_id}/students')
async def get_enrolled_students(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)
    return await build_student_course_progress_report(course_id, school_id, db)

@router.get('/{course_id}/students/progress')
async def get_course_students_progress_report(course_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)
    students = await build_student_course_progress_report(course_id, school_id, db)
    completed_students = sum((1 for student in students if student['status'] == 'COMPLETED'))
    in_progress_students = sum((1 for student in students if student['status'] == 'IN_PROGRESS'))
    not_started_students = sum((1 for student in students if student['status'] == 'NOT_STARTED'))
    return {'course': await _course_payload(db, course), 'total_students': len(students), 'average_progress': round(sum((student['progress'] for student in students)) / len(students), 2) if students else 0, 'completed_students': completed_students, 'in_progress_students': in_progress_students, 'not_started_students': not_started_students, 'total_lessons': students[0]['total_lessons'] if students else await async_query(db, Lesson).filter(Lesson.course_id == course_id).count(), 'students': students}
