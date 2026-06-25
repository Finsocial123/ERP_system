from __future__ import annotations
from fastapi import HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.academic import AcademicSession, SchoolClass, Subject
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.user import User, UserRole
from app.core.async_query import async_query
from app.core.sections import validate_class_section_name
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
MANAGER_ROLES = (UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER)
LEARNER_ROLES = (UserRole.STUDENT, UserRole.PARENT)
ONLY_STUDENT_ROLES = UserRole.STUDENT
ALL_LMS_ROLES = (UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER, UserRole.STUDENT, UserRole.PARENT)

async def current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    active = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True)).order_by(AcademicSession.id.desc()).first()
    if active:
        return active
    return await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()

async def teacher_for_user(db: AsyncSession, school_id: int, user: User) -> Teacher | None:
    teacher = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.user_id == user.id).first()
    if teacher:
        return teacher
    conditions = []
    if user.email:
        conditions.append(Teacher.email == user.email)
    if user.phone:
        conditions.append(Teacher.phone == user.phone)
    if user.login_id:
        conditions.append(Teacher.employee_id == user.login_id)
    if not conditions:
        return None
    return await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True), or_(*conditions)).first()

# async def student_for_user(db: AsyncSession, school_id: int, user: User) -> Student | None:
#     student = await async_query(db, Student).options(joinedload(Student.school_class), joinedload(Student.section)).filter(Student.school_id == school_id, Student.user_id == user.id).first()
#     if student:
#         return student
#     conditions = []
#     if user.email:
#         conditions.append(Student.email == user.email)
#     if user.phone:
#         conditions.append(Student.phone == user.phone)
#     if user.login_id:
#         conditions.append(Student.admission_no == user.login_id)
#     if not conditions:
#         return None
#     return await async_query(db, Student).options(joinedload(Student.school_class), joinedload(Student.section)).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(*conditions)).first()



async def student_for_user(db: AsyncSession, school_id: int, user: User) -> Student | None:
    # Get current active session first
    active_session = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active.is_(True)
    ).first()
    
    session_filter = (
        [Student.academic_session_id == active_session.id] 
        if active_session else []
    )

    student = await async_query(db, Student).options(
        joinedload(Student.school_class), 
        joinedload(Student.section)
    ).filter(
        Student.school_id == school_id, 
        Student.user_id == user.id,
        *session_filter
    ).first()
    
    if student:
        return student

    # Fallback: match by email/phone/admission_no
    conditions = []
    if user.email:
        conditions.append(Student.email == user.email)
    if user.phone:
        conditions.append(Student.phone == user.phone)
    if user.login_id:
        conditions.append(Student.admission_no == user.login_id)
    if not conditions:
        return None

    return await async_query(db, Student).options(
        joinedload(Student.school_class), 
        joinedload(Student.section)
    ).filter(
        Student.school_id == school_id, 
        Student.is_active.is_(True),
        *session_filter,
        or_(*conditions)
    ).first()


async def children_for_parent(db: AsyncSession, school_id: int, user: User) -> list[Student]:
    guardians = []
    if user.id:
        guardians = await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == school_id, ParentGuardian.user_id == user.id, ParentGuardian.is_active.is_(True)).all()
    if not guardians:
        conditions = []
        if user.email:
            conditions.append(ParentGuardian.email == user.email)
        if user.phone:
            conditions.append(ParentGuardian.phone == user.phone)
        if conditions:
            guardians = await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == school_id, ParentGuardian.is_active.is_(True), or_(*conditions)).all()
    guardian_ids = [guardian.id for guardian in guardians]
    if not guardian_ids:
        return []
    return await async_query(db, Student).options(joinedload(Student.school_class)).filter(Student.school_id == school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True)).order_by(Student.first_name.asc(), Student.id.asc()).all()

def full_student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name or ''}".strip()

async def validate_same_school(db: AsyncSession, model, item_id: int | None, school_id: int, field_name: str):
    if item_id is None:
        return None
    item = await async_query(db, model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f'{field_name} not found for this school')
    return item

async def validate_course_scope(db: AsyncSession, school_id: int, class_id: int, section_id: int | None, subject_id: int | None, section_name: str | None = None):
    school_class = await validate_same_school(db, SchoolClass, class_id, school_id, 'Class')
    resolved_section_name = await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id)
    subject = await validate_same_school(db, Subject, subject_id, school_id, 'Subject')
    if subject and subject.class_id != class_id:
        raise HTTPException(status_code=400, detail='Selected subject is not assigned to the selected class')
    return (school_class, resolved_section_name, subject)

async def teacher_has_scope(db: AsyncSession, school_id: int, teacher: Teacher, class_id: int, section_id: int | None, subject_id: int | None, section_name: str | None = None) -> bool:
    subject_query = async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id)
    assignment_count = await subject_query.count() + await async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id).count()
    if assignment_count == 0:
        return True
    subject_match_query = subject_query.filter(or_(TeacherSubject.class_id == class_id, TeacherSubject.class_id.is_(None)), or_(TeacherSubject.section_name == section_name, TeacherSubject.section_name.is_(None)))
    if subject_id is not None:
        subject_match_query = subject_match_query.filter(TeacherSubject.subject_id == subject_id)
    subject_match = await subject_match_query.first()
    if subject_match:
        return True
    class_teacher_match = await async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id, ClassTeacherAssignment.class_id == class_id, or_(ClassTeacherAssignment.section_name == section_name, ClassTeacherAssignment.section_name.is_(None))).first()
    return bool(class_teacher_match)

def course_matches_student(course: Course, student: Student) -> bool:
    """Match LMS courses across academic sessions.

    Courses remain global, while classes/sections are duplicated per session.
    Prefer direct id matches, then fall back to matching the replicated
    class/section names when relationships are already loaded.
    """
    if course.school_id != student.school_id:
        return False
    if course.class_id is None or student.class_id is None:
        return False

    class_matches = course.class_id == student.class_id
    if not class_matches:
        course_class = course.__dict__.get("school_class")
        student_class = student.__dict__.get("school_class")
        class_matches = bool(course_class and student_class and course_class.name == student_class.name)
    if not class_matches:
        return False

    if not course.section_name and course.section_id is None:
        return True
    if course.section_name:
        return (student.section_name or "").casefold() == course.section_name.casefold()
    return course.section_id == student.section_id

async def get_course_or_404(db: AsyncSession, school_id: int, course_id: int) -> Course:
    # Load every relationship used by the LMS course detail/payload code up front.
    # In AsyncSession, touching an unloaded relationship later (course.teacher,
    # course.subject, etc.) triggers lazy I/O and raises MissingGreenlet.
    course = await async_query(db, Course).options(
        joinedload(Course.teacher),
        joinedload(Course.school_class),
        joinedload(Course.subject),
        joinedload(Course.academic_session),
    ).filter(Course.id == course_id, Course.school_id == school_id, Course.is_active.is_(True)).first()
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')
    return course

async def can_manage_course(db: AsyncSession, school_id: int, user: User, course: Course) -> bool:
    if course.school_id != school_id:
        return False
    if user.role in ADMIN_ROLES:
        return True
    if user.role != UserRole.TEACHER.value:
        return False
    if course.teacher_id == user.id:
        return True
    teacher = await teacher_for_user(db, school_id, user)
    if not teacher or course.class_id is None:
        return False
    return await teacher_has_scope(db, school_id, teacher, course.class_id, course.section_id, course.subject_id, course.section_name)

async def ensure_can_manage_course(db: AsyncSession, school_id: int, user: User, course: Course) -> None:
    if not await can_manage_course(db, school_id, user, course):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You can manage only your assigned LMS courses')

async def can_view_course(db: AsyncSession, school_id: int, user: User, course: Course) -> bool:
    if course.school_id != school_id or not course.is_active:
        return False
    if await can_manage_course(db, school_id, user, course):
        return True
    if user.role == UserRole.STUDENT.value:
        student = await student_for_user(db, school_id, user)
        return bool(student and course_matches_student(course, student))
    if user.role == UserRole.PARENT.value:
        return any((course_matches_student(course, child) for child in await children_for_parent(db, school_id, user)))
    return False

async def ensure_can_view_course(db: AsyncSession, school_id: int, user: User, course: Course) -> None:
    if not await can_view_course(db, school_id, user, course):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='This LMS course is not available for your role/profile')

async def ensure_enrollment_for_user_student(db: AsyncSession, school_id: int, user: User, course: Course) -> Enrollment:
    if user.role != UserRole.STUDENT.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Student access required')
    student = await student_for_user(db, school_id, user)
    if not student or not course_matches_student(course, student):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='This course is not assigned to your class or section')
    enrollment = await async_query(db, Enrollment).filter(Enrollment.student_id == user.id, Enrollment.course_id == course.id).first()
    if not enrollment:
        enrollment = Enrollment(student_id=user.id, course_id=course.id, progress=0)
        db.add(enrollment)
        await db.commit()
        await db.refresh(enrollment)
    return enrollment

async def async_get_course_or_404(db: AsyncSession, school_id: int, course_id: int) -> Course:
    result = await db.execute(
        select(Course)
        .options(
            joinedload(Course.teacher),
            joinedload(Course.school_class),
                joinedload(Course.subject),
            joinedload(Course.academic_session),
        )
        .where(Course.id == course_id, Course.school_id == school_id, Course.is_active.is_(True))
    )
    course = result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')
    return course

async def async_teacher_for_user(db: AsyncSession, school_id: int, user: User) -> Teacher | None:
    result = await db.execute(select(Teacher).where(Teacher.school_id == school_id, Teacher.user_id == user.id))
    teacher = result.scalars().first()
    if teacher:
        return teacher
    conditions = []
    if user.email:
        conditions.append(Teacher.email == user.email)
    if user.phone:
        conditions.append(Teacher.phone == user.phone)
    if user.login_id:
        conditions.append(Teacher.employee_id == user.login_id)
    if not conditions:
        return None
    result = await db.execute(select(Teacher).where(Teacher.school_id == school_id, Teacher.is_active.is_(True), or_(*conditions)))
    return result.scalars().first()

async def async_teacher_has_scope(db: AsyncSession, school_id: int, teacher: Teacher, class_id: int, section_id: int | None, subject_id: int | None, section_name: str | None = None) -> bool:
    subject_count_result = await db.execute(select(func.count()).select_from(TeacherSubject).where(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id))
    subject_count = subject_count_result.scalar()
    class_count_result = await db.execute(select(func.count()).select_from(ClassTeacherAssignment).where(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id))
    class_count = class_count_result.scalar()
    if subject_count + class_count == 0:
        return True
    subject_match_query = select(TeacherSubject).where(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id, or_(TeacherSubject.class_id == class_id, TeacherSubject.class_id.is_(None)), or_(TeacherSubject.section_name == section_name, TeacherSubject.section_name.is_(None)))
    if subject_id is not None:
        subject_match_query = subject_match_query.where(TeacherSubject.subject_id == subject_id)
    subject_result = await db.execute(subject_match_query)
    if subject_result.scalars().first():
        return True
    class_result = await db.execute(select(ClassTeacherAssignment).where(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id, ClassTeacherAssignment.class_id == class_id, or_(ClassTeacherAssignment.section_name == section_name, ClassTeacherAssignment.section_name.is_(None))))
    return bool(class_result.scalars().first())

async def async_can_manage_course(db: AsyncSession, school_id: int, user: User, course: Course) -> bool:
    if course.school_id != school_id:
        return False
    if user.role in ADMIN_ROLES:
        return True
    if user.role != UserRole.TEACHER.value:
        return False
    if course.teacher_id == user.id:
        return True
    teacher = await async_teacher_for_user(db, school_id, user)
    if not teacher or course.class_id is None:
        return False
    return await async_teacher_has_scope(db, school_id, teacher, course.class_id, course.section_id, course.subject_id, course.section_name)

async def async_ensure_can_manage_course(db: AsyncSession, school_id: int, user: User, course: Course) -> None:
    if not await async_can_manage_course(db, school_id, user, course):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You can manage only your assigned LMS courses')

async def async_current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    active = (await db.execute(select(AcademicSession).where(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True)).order_by(AcademicSession.id.desc()))).scalars().first()
    if active:
        return active
    return (await db.execute(select(AcademicSession).where(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()))).scalars().first()
