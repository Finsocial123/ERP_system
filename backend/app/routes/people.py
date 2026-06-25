from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.meetings import TeacherClassOut
from app.core.database import get_async_db
from app.core.async_query import async_query
from app.core.security import get_password_hash
from app.core.sections import validate_class_section_name, virtual_section_id_for_name
from app.core.utils import generate_temporary_password, normalize_login_id
from app.dependencies.academic_session import selected_academic_session_id, require_writable_academic_session, writable_selected_academic_session_id, assert_item_session_is_writable
from app.dependencies.auth import current_school_id, require_school_admin, get_current_user
from app.schemas.notice import AvailableClassOut
from app.models.academic import AcademicSession, Department, SchoolClass, Subject, SchoolClass
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.people import ClassTeacherCreate, ClassTeacherRead, ParentLoginCreate, StudentCreate, StudentRead, StudentUpdate, TeacherCreate, TeacherRead, TeacherSubjectCreate, TeacherSubjectRead, TeacherUpdate
router = APIRouter(tags=['Phase 2 - Student and Teacher Management'], dependencies=[Depends(require_writable_academic_session)])
ADMIN_ROLE_VALUES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}

def _with_read_relationships(query, model):
    # Pydantic response serialization runs outside SQLAlchemy's async IO context.
    # Any relationship included in a response model must be eagerly loaded here,
    # otherwise FastAPI/Pydantic triggers MissingGreenlet while reading it.
    if model is Student:
        return query.options(selectinload(Student.guardian))
    return query


async def _get_or_404(db: AsyncSession, model, item_id: int, school_id: int):
    query = _with_read_relationships(async_query(db, model), model)
    item = await query.filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f'{model.__name__} not found')
    return item

async def _validate_same_school(db: AsyncSession, model, item_id: int | None, school_id: int, field_name: str):
    if item_id is None:
        return None
    item = await async_query(db, model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f'{field_name} not found for this school')
    return item

async def _resolve_section_name(db: AsyncSession, school_id: int, class_id: int | None, section_name: str | None, section_id: int | None, session_id: int | None = None) -> str | None:
    return await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id, session_id=session_id)

async def _commit_or_duplicate(db: AsyncSession, duplicate_message: str):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=duplicate_message)

async def _school_slug(db: AsyncSession, school_id: int) -> str:
    school = await db.get(School, school_id)
    return school.slug if school else f'school-{school_id}'

def _synthetic_email(login_id: str, school_slug: str, role: str) -> str:
    safe_id = normalize_login_id(login_id).lower().replace('@', '-')
    return f'{safe_id}@{school_slug}.{role.lower()}.local'

async def _ensure_login_id_available(db: AsyncSession, school_id: int, login_id: str, exclude_user_id: int | None=None):
    normalized = normalize_login_id(login_id)
    query = async_query(db, User).filter(User.school_id == school_id, User.login_id == normalized)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if await query.first():
        raise HTTPException(status_code=409, detail='A user with this login ID already exists in this school')
    return normalized

def _parent_login_candidates(guardian: ParentGuardian, fallback_seed: str) -> list[str]:
    """Build safe parent login candidates.

    Do not use phone number as a parent login identifier. In demo/real data,
    many guardians can share a placeholder or family phone number, and using it
    can wrongly link multiple guardians to the same parent user.
    """
    candidates: list[str] = []
    for value in (guardian.email, f'{fallback_seed}-PARENT', f'PARENT-{fallback_seed}'):
        if value and str(value).strip():
            normalized = normalize_login_id(str(value))
            if normalized and normalized not in candidates:
                candidates.append(normalized)
    return candidates

async def _ensure_parent_login(db: AsyncSession, school_id: int, guardian: ParentGuardian, fallback_seed: str, password: str | None=None) -> tuple[User | None, str | None]:
    """Create or link a parent portal user for a guardian.

    Returns (user, temporary_password). temporary_password is only returned when a
    new login is created. If a matching parent user already exists, the guardian
    is linked to it without changing that user's password.
    """
    if guardian.user_id:
        return (await db.get(User, guardian.user_id), None)
    school_slug = await _school_slug(db, school_id)
    candidate_login_ids = _parent_login_candidates(guardian, fallback_seed)
    if guardian.id:
        candidate_login_ids.append(normalize_login_id(f'{fallback_seed}-PARENT-{guardian.id}'))
    selected_login_id: str | None = None
    for login_id in candidate_login_ids:
        existing = await async_query(db, User).filter(User.school_id == school_id, User.login_id == login_id).first()
        if not existing:
            selected_login_id = login_id
            break
        if existing.role == UserRole.PARENT.value:
            guardian.user_id = existing.id
            return (existing, None)
    if not selected_login_id:
        selected_login_id = normalize_login_id(f"PARENT-{fallback_seed}-{guardian.id or 'NEW'}")
        suffix = 1
        base_login_id = selected_login_id
        while await async_query(db, User).filter(User.school_id == school_id, User.login_id == selected_login_id).first():
            suffix += 1
            selected_login_id = normalize_login_id(f'{base_login_id}-{suffix}')
    temporary_password = password or generate_temporary_password()
    user = User(school_id=school_id, full_name=guardian.full_name, email=str(guardian.email).lower() if guardian.email else _synthetic_email(selected_login_id, school_slug, 'parent'), phone=guardian.phone, login_id=selected_login_id, hashed_password=get_password_hash(temporary_password), role=UserRole.PARENT.value, must_change_password=True)
    db.add(user)
    await db.flush()
    guardian.user_id = user.id
    return (user, temporary_password)

@router.get('/students', response_model=list[StudentRead])
async def list_students(request: Request, search: str | None=Query(default=None), class_id: int | None=Query(default=None), section_id: int | None=Query(default=None), status_value: str | None=Query(default=None, alias='status'), include_inactive: bool=Query(default=False), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    query = async_query(db, Student).options(selectinload(Student.guardian)).filter(Student.school_id == school_id)
    can_view_inactive = current_user.role in ADMIN_ROLE_VALUES
    if not include_inactive or not can_view_inactive:
        query = query.filter(Student.is_active.is_(True))
    if session_id is not None:
        query = query.filter(Student.academic_session_id == session_id)
    if search:
        like = f'%{search.strip()}%'
        query = query.filter(or_(Student.first_name.ilike(like), Student.last_name.ilike(like), Student.admission_no.ilike(like), Student.roll_number.ilike(like), Student.email.ilike(like)))
    if class_id is not None:
        query = query.filter(Student.class_id == class_id)
    if section_id is not None and class_id is not None:
        section_name = await _resolve_section_name(db, school_id, class_id, None, section_id, session_id)
        query = query.filter(Student.section_name == section_name)
    elif section_id is not None:
        query = query.filter(Student.section_id == section_id)
    if status_value:
        query = query.filter(Student.status == status_value.upper())
    return await query.order_by(Student.id.desc()).all()

@router.post('/students', response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreate, request: Request, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    session_id = await writable_selected_academic_session_id(db, school_id, request=request, current_user=current_user, explicit_session_id=payload.academic_session_id)
    await _validate_same_school(db, SchoolClass, payload.class_id, school_id, 'Class')
    resolved_section_name = await _resolve_section_name(db, school_id, payload.class_id, payload.section_name, payload.section_id, session_id)
    if payload.create_parent_login and (not payload.guardian):
        raise HTTPException(status_code=400, detail='Add parent/guardian details before creating a parent login')
    guardian = None
    parent_user = None
    parent_temporary_password = None
    if payload.guardian:
        guardian = ParentGuardian(school_id=school_id, **payload.guardian.model_dump(exclude_none=True))
        db.add(guardian)
        await db.flush()
        if payload.create_parent_login:
            parent_user, parent_temporary_password = await _ensure_parent_login(db, school_id, guardian, payload.admission_no, payload.parent_password)
    user_id = None
    temporary_password = None
    if payload.create_login:
        login_id = await _ensure_login_id_available(db, school_id, payload.admission_no)
        temporary_password = payload.password or generate_temporary_password()
        full_name = f"{payload.first_name} {payload.last_name or ''}".strip()
        school_slug = await _school_slug(db, school_id)
        user = User(school_id=school_id, full_name=full_name, email=str(payload.email).lower() if payload.email else _synthetic_email(payload.admission_no, school_slug, 'student'), phone=payload.phone, login_id=login_id, hashed_password=get_password_hash(temporary_password), role=UserRole.STUDENT.value, must_change_password=True)
        db.add(user)
        await db.flush()
        user_id = user.id
    data = payload.model_dump(exclude={'guardian', 'create_login', 'password', 'create_parent_login', 'parent_password'})
    data['academic_session_id'] = session_id
    data['section_id'] = None
    data['section_name'] = resolved_section_name
    student = Student(school_id=school_id, guardian_id=guardian.id if guardian else None, user_id=user_id, **data)
    db.add(student)
    await _commit_or_duplicate(db, 'Student admission number already exists in this school')
    student = await _get_or_404(db, Student, student.id, school_id)
    student.temporary_password = temporary_password
    student.parent_temporary_password = parent_temporary_password
    if parent_user:
        student.parent_login_id = parent_user.login_id
    elif guardian and guardian.user_id:
        linked_parent = await db.get(User, guardian.user_id)
        student.parent_login_id = linked_parent.login_id if linked_parent else None
    return student

@router.get('/students/{student_id}', response_model=StudentRead)
async def get_student(student_id: int, school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    return await _get_or_404(db, Student, student_id, school_id)

@router.post('/students/{student_id}/parent-login', response_model=StudentRead)
async def create_parent_login_for_student(student_id: int, payload: ParentLoginCreate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    student = await _get_or_404(db, Student, student_id, school_id)
    await assert_item_session_is_writable(db, school_id, student)
    if not student.guardian:
        raise HTTPException(status_code=400, detail='This student has no parent/guardian details')
    parent_user, temporary_password = await _ensure_parent_login(db, school_id, student.guardian, student.admission_no, payload.password)
    await db.commit()
    student = await _get_or_404(db, Student, student.id, school_id)
    student.parent_temporary_password = temporary_password
    student.parent_login_id = parent_user.login_id if parent_user else None
    return student

@router.put('/students/{student_id}', response_model=StudentRead)
async def update_student(student_id: int, payload: StudentUpdate, request: Request, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    student = await _get_or_404(db, Student, student_id, school_id)
    await assert_item_session_is_writable(db, school_id, student)
    values = payload.model_dump(exclude_unset=True, exclude={'guardian', 'create_parent_login', 'parent_password'})
    if 'academic_session_id' in values:
        values['academic_session_id'] = await writable_selected_academic_session_id(db, school_id, request=request, current_user=current_user, explicit_session_id=values.get('academic_session_id'))
    class_id = values.get('class_id', student.class_id)
    section_id = values.get('section_id', student.section_id)
    incoming_section_name = values.get('section_name', student.section_name)
    if 'class_id' in values:
        await _validate_same_school(db, SchoolClass, values.get('class_id'), school_id, 'Class')
    if 'section_id' in values or 'section_name' in values or 'class_id' in values:
        values['section_name'] = await _resolve_section_name(db, school_id, class_id, incoming_section_name, section_id, values.get('academic_session_id', student.academic_session_id))
        values['section_id'] = None
    if 'admission_no' in values and student.user_id:
        await _ensure_login_id_available(db, school_id, values['admission_no'], exclude_user_id=student.user_id)
    for key, value in values.items():
        setattr(student, key, value)
    parent_user = None
    parent_temporary_password = None
    if payload.guardian is not None:
        guardian_values = payload.guardian.model_dump(exclude_unset=True)
        if student.guardian:
            for key, value in guardian_values.items():
                setattr(student.guardian, key, value)
        elif guardian_values.get('full_name'):
            guardian = ParentGuardian(school_id=school_id, **guardian_values)
            db.add(guardian)
            await db.flush()
            student.guardian = guardian
    if payload.create_parent_login:
        if not student.guardian:
            raise HTTPException(status_code=400, detail='Add parent/guardian details before creating a parent login')
        parent_user, parent_temporary_password = await _ensure_parent_login(db, school_id, student.guardian, student.admission_no, payload.parent_password)
    if student.user_id:
        user = await db.get(User, student.user_id)
        if user:
            user.full_name = f"{student.first_name} {student.last_name or ''}".strip()
            user.phone = student.phone
            user.login_id = normalize_login_id(student.admission_no)
            if student.email:
                user.email = str(student.email).lower()
            user.is_active = student.is_active
    await _commit_or_duplicate(db, 'Student admission number already exists in this school')
    student = await _get_or_404(db, Student, student.id, school_id)
    student.parent_temporary_password = parent_temporary_password
    if payload.create_parent_login:
        if parent_user:
            student.parent_login_id = parent_user.login_id
        elif student.guardian and student.guardian.user_id:
            linked_parent = await db.get(User, student.guardian.user_id)
            student.parent_login_id = linked_parent.login_id if linked_parent else None
    return student

@router.patch('/students/{student_id}/suspend', response_model=StudentRead)
async def suspend_student(student_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    student = await _get_or_404(db, Student, student_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, student)
    student.status = 'SUSPENDED'
    student.is_active = False
    if student.user_id:
        user = await db.get(User, student.user_id)
        if user:
            user.is_active = False
    await db.commit()
    return await _get_or_404(db, Student, student.id, current_user.school_id)

@router.patch('/students/{student_id}/activate', response_model=StudentRead)
async def activate_student(student_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    student = await _get_or_404(db, Student, student_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, student)
    student.status = 'ACTIVE'
    student.is_active = True
    if student.user_id:
        user = await db.get(User, student.user_id)
        if user:
            user.is_active = True
    await db.commit()
    return await _get_or_404(db, Student, student.id, current_user.school_id)

@router.delete('/students/{student_id}', response_model=MessageResponse)
async def delete_student(student_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    student = await _get_or_404(db, Student, student_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, student)
    student.status = 'DELETED'
    student.is_active = False
    if student.user_id:
        user = await db.get(User, student.user_id)
        if user:
            user.is_active = False
    await db.commit()
    return {'message': 'Student deactivated'}

@router.get('/teachers', response_model=list[TeacherRead])
async def list_teachers(request: Request, search: str | None=Query(default=None), department_id: int | None=Query(default=None), status_value: str | None=Query(default=None, alias='status'), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    query = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True))
    if session_id is not None:
        query = query.filter(Teacher.academic_session_id == session_id)
    if search:
        like = f'%{search.strip()}%'
        query = query.filter(or_(Teacher.full_name.ilike(like), Teacher.employee_id.ilike(like), Teacher.email.ilike(like), Teacher.phone.ilike(like)))
    if department_id is not None:
        query = query.filter(Teacher.department_id == department_id)
    if status_value:
        query = query.filter(Teacher.status == status_value.upper())
    return await query.order_by(Teacher.id.desc()).all()

@router.post('/teachers', response_model=TeacherRead, status_code=status.HTTP_201_CREATED)
async def create_teacher(payload: TeacherCreate, request: Request, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    session_id = await writable_selected_academic_session_id(db, school_id, request=request, current_user=current_user, explicit_session_id=payload.academic_session_id)
    await _validate_same_school(db, Department, payload.department_id, school_id, 'Department')
    user_id = None
    temporary_password = None
    if payload.create_login:
        login_id = await _ensure_login_id_available(db, school_id, payload.employee_id)
        temporary_password = payload.password or generate_temporary_password()
        school_slug = await _school_slug(db, school_id)
        user = User(school_id=school_id, full_name=payload.full_name, email=str(payload.email).lower() if payload.email else _synthetic_email(payload.employee_id, school_slug, 'teacher'), phone=payload.phone, login_id=login_id, hashed_password=get_password_hash(temporary_password), role=UserRole.TEACHER.value, must_change_password=True)
        db.add(user)
        await db.flush()
        user_id = user.id
    data = payload.model_dump(exclude={'create_login', 'password'})
    data['academic_session_id'] = session_id
    teacher = Teacher(school_id=school_id, user_id=user_id, **data)
    db.add(teacher)
    await _commit_or_duplicate(db, 'Teacher employee ID already exists in this school')
    await db.refresh(teacher)
    teacher.temporary_password = temporary_password
    return teacher

@router.get('/teachers/class-teachers', response_model=list[ClassTeacherRead])
async def list_class_teachers(request: Request, school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    session_id = await selected_academic_session_id(db, school_id, request=request)
    query = async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id)
    if session_id is not None:
        query = query.filter(ClassTeacherAssignment.academic_session_id == session_id)
    return await query.order_by(ClassTeacherAssignment.id.desc()).all()

@router.post('/teachers/class-teachers', response_model=ClassTeacherRead, status_code=status.HTTP_201_CREATED)
async def assign_class_teacher(payload: ClassTeacherCreate, request: Request, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    session_id = await writable_selected_academic_session_id(db, school_id, request=request, current_user=current_user, explicit_session_id=payload.academic_session_id)
    teacher = await _get_or_404(db, Teacher, payload.teacher_id, school_id)
    await assert_item_session_is_writable(db, school_id, teacher)
    await _validate_same_school(db, SchoolClass, payload.class_id, school_id, 'Class')
    await _validate_same_school(db, AcademicSession, session_id, school_id, 'Academic session')
    resolved_section_name = await _resolve_section_name(db, school_id, payload.class_id, payload.section_name, payload.section_id, session_id)
    section_filter = ClassTeacherAssignment.section_name.is_(None) if resolved_section_name is None else ClassTeacherAssignment.section_name == resolved_section_name
    existing = await async_query(db, ClassTeacherAssignment).filter(
        ClassTeacherAssignment.school_id == school_id,
        ClassTeacherAssignment.class_id == payload.class_id,
        ClassTeacherAssignment.academic_session_id == session_id,
        section_filter,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail='This class already has a class teacher for the selected session')
    data = payload.model_dump()
    data['academic_session_id'] = session_id
    data['section_id'] = None
    data['section_name'] = resolved_section_name
    assignment = ClassTeacherAssignment(school_id=school_id, **data)
    db.add(assignment)
    await _commit_or_duplicate(db, 'This class already has a class teacher for the selected session')
    await db.refresh(assignment)
    return assignment

@router.delete('/teachers/class-teachers/{assignment_id}', response_model=MessageResponse)
async def delete_class_teacher_assignment(assignment_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    assignment = await _get_or_404(db, ClassTeacherAssignment, assignment_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, assignment)
    await db.delete(assignment)
    await db.commit()
    return {'message': 'Class teacher assignment removed'}

@router.delete('/teachers/subject-assignments/{assignment_id}', response_model=MessageResponse)
async def delete_teacher_subject_assignment(assignment_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    assignment = await _get_or_404(db, TeacherSubject, assignment_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, assignment)
    await db.delete(assignment)
    await db.commit()
    return {'message': 'Teacher subject assignment removed'}

@router.get('/teachers/me/classes', response_model=list[TeacherClassOut])
async def get_my_classes(request: Request, current_user: User=Depends(get_current_user), school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    teacher_query = async_query(db, Teacher).filter(Teacher.user_id == current_user.id, Teacher.school_id == school_id, Teacher.is_active.is_(True))
    if session_id is not None:
        teacher_query = teacher_query.filter(Teacher.academic_session_id == session_id)
    teacher = await teacher_query.first()
    if not teacher:
        raise HTTPException(404, 'No teacher profile found for this user')
    aq = async_query(db, TeacherSubject).options(joinedload(TeacherSubject.school_class), joinedload(TeacherSubject.subject)).filter(TeacherSubject.teacher_id == teacher.id, TeacherSubject.school_id == school_id)
    if session_id is not None:
        aq = aq.filter(TeacherSubject.academic_session_id == session_id)
    assignments = await aq.order_by(TeacherSubject.class_id, TeacherSubject.section_name).all()
    rows = []
    for a in assignments:
        rows.append({'class_id': a.class_id, 'class_name': a.school_class.name if a.school_class else f'Class {a.class_id}', 'section_id': await virtual_section_id_for_name(db, school_id, a.class_id, a.section_name, session_id), 'section_name': a.section_name, 'subject_id': a.subject_id, 'subject_name': a.subject.name if a.subject else f'Subject {a.subject_id}'})
    return rows

@router.get('/teachers/me/available-classes', response_model=list[AvailableClassOut])
async def get_teacher_available_classes(request: Request, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.TEACHER.value:
        return []
    session_id = await selected_academic_session_id(db, current_user.school_id, request=request, current_user=current_user)
    teacher_stmt = select(Teacher).where(Teacher.user_id == current_user.id, Teacher.school_id == current_user.school_id, Teacher.is_active.is_(True))
    if session_id is not None:
        teacher_stmt = teacher_stmt.where(Teacher.academic_session_id == session_id)
    result = await db.execute(teacher_stmt)
    teacher = result.scalar_one_or_none()
    if not teacher:
        return []
    subject_classes = select(TeacherSubject.class_id, TeacherSubject.section_id, TeacherSubject.section_name).where(TeacherSubject.teacher_id == teacher.id, TeacherSubject.school_id == current_user.school_id)
    class_teacher_classes = select(ClassTeacherAssignment.class_id, ClassTeacherAssignment.section_id, ClassTeacherAssignment.section_name).where(ClassTeacherAssignment.teacher_id == teacher.id, ClassTeacherAssignment.school_id == current_user.school_id)
    if session_id is not None:
        subject_classes = subject_classes.where(TeacherSubject.academic_session_id == session_id)
        class_teacher_classes = class_teacher_classes.where(ClassTeacherAssignment.academic_session_id == session_id)
    combined = subject_classes.union(class_teacher_classes)
    pairs_result = await db.execute(combined)
    pairs = pairs_result.all()
    if not pairs:
        return []
    class_ids = {p.class_id for p in pairs}
    classes_result = await db.execute(select(SchoolClass).where(SchoolClass.id.in_(class_ids)))
    classes_map = {c.id: c.name for c in classes_result.scalars().all()}
    rows = []
    for p in sorted(pairs, key=lambda x: (x.class_id, x.section_name or '')):
        rows.append(AvailableClassOut(class_id=p.class_id, class_name=classes_map.get(p.class_id, f'Class {p.class_id}'), section_id=await virtual_section_id_for_name(db, current_user.school_id, p.class_id, p.section_name, session_id), section_name=p.section_name))
    return rows

@router.get('/teachers/{teacher_id}', response_model=TeacherRead)
async def get_teacher(teacher_id: int, school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    return await _get_or_404(db, Teacher, teacher_id, school_id)

@router.put('/teachers/{teacher_id}', response_model=TeacherRead)
async def update_teacher(teacher_id: int, payload: TeacherUpdate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id)
    await assert_item_session_is_writable(db, school_id, teacher)
    values = payload.model_dump(exclude_unset=True)
    if 'academic_session_id' in values:
        values['academic_session_id'] = await writable_selected_academic_session_id(db, school_id, request=None, current_user=current_user, explicit_session_id=values.get('academic_session_id'))
    if 'department_id' in values:
        await _validate_same_school(db, Department, values.get('department_id'), school_id, 'Department')
    if 'employee_id' in values and teacher.user_id:
        await _ensure_login_id_available(db, school_id, values['employee_id'], exclude_user_id=teacher.user_id)
    for key, value in values.items():
        setattr(teacher, key, value)
    if teacher.user_id:
        user = await db.get(User, teacher.user_id)
        if user:
            user.full_name = teacher.full_name
            user.phone = teacher.phone
            user.login_id = normalize_login_id(teacher.employee_id)
            if teacher.email:
                user.email = str(teacher.email).lower()
            user.is_active = teacher.is_active
    await _commit_or_duplicate(db, 'Teacher employee ID already exists in this school')
    await db.refresh(teacher)
    return teacher

@router.patch('/teachers/{teacher_id}/suspend', response_model=TeacherRead)
async def suspend_teacher(teacher_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    teacher = await _get_or_404(db, Teacher, teacher_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, teacher)
    teacher.status = 'SUSPENDED'
    teacher.is_active = False
    if teacher.user_id:
        user = await db.get(User, teacher.user_id)
        if user:
            user.is_active = False
    await db.commit()
    await db.refresh(teacher)
    return teacher

@router.patch('/teachers/{teacher_id}/activate', response_model=TeacherRead)
async def activate_teacher(teacher_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    teacher = await _get_or_404(db, Teacher, teacher_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, teacher)
    teacher.status = 'ACTIVE'
    teacher.is_active = True
    if teacher.user_id:
        user = await db.get(User, teacher.user_id)
        if user:
            user.is_active = True
    await db.commit()
    await db.refresh(teacher)
    return teacher

@router.delete('/teachers/{teacher_id}', response_model=MessageResponse)
async def delete_teacher(teacher_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    teacher = await _get_or_404(db, Teacher, teacher_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, teacher)
    teacher.status = 'DELETED'
    teacher.is_active = False
    if teacher.user_id:
        user = await db.get(User, teacher.user_id)
        if user:
            user.is_active = False
    await db.commit()
    return {'message': 'Teacher deactivated'}

@router.get('/teachers/{teacher_id}/subjects', response_model=list[TeacherSubjectRead])
async def list_teacher_subjects(teacher_id: int, request: Request, school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    await _get_or_404(db, Teacher, teacher_id, school_id)
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    query = async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher_id)
    if session_id is not None:
        query = query.filter(TeacherSubject.academic_session_id == session_id)
    return await query.order_by(TeacherSubject.id.desc()).all()

@router.post('/teachers/{teacher_id}/subjects', response_model=TeacherSubjectRead, status_code=status.HTTP_201_CREATED)
async def assign_teacher_subject(teacher_id: int, payload: TeacherSubjectCreate, request: Request, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    school_id = current_user.school_id
    session_id = await writable_selected_academic_session_id(db, school_id, request=request, current_user=current_user, explicit_session_id=payload.academic_session_id)
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id)
    await assert_item_session_is_writable(db, school_id, teacher)
    subject = await _validate_same_school(db, Subject, payload.subject_id, school_id, 'Subject')
    await _validate_same_school(db, SchoolClass, payload.class_id, school_id, 'Class')
    resolved_section_name = await _resolve_section_name(db, school_id, payload.class_id, payload.section_name, payload.section_id, session_id)
    if subject and subject.class_id != payload.class_id:
        raise HTTPException(status_code=400, detail='Selected subject does not belong to selected class')
    section_filter = TeacherSubject.section_name.is_(None) if resolved_section_name is None else TeacherSubject.section_name == resolved_section_name
    existing = await async_query(db, TeacherSubject).filter(
        TeacherSubject.school_id == school_id,
        TeacherSubject.teacher_id == teacher_id,
        TeacherSubject.subject_id == payload.subject_id,
        TeacherSubject.class_id == payload.class_id,
        TeacherSubject.academic_session_id == session_id,
        section_filter,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail='This teacher-subject assignment already exists')
    data = payload.model_dump()
    data['academic_session_id'] = session_id
    data['section_id'] = None
    data['section_name'] = resolved_section_name
    assignment = TeacherSubject(school_id=school_id, teacher_id=teacher_id, **data)
    db.add(assignment)
    await _commit_or_duplicate(db, 'This teacher-subject assignment already exists')
    await db.refresh(assignment)
    return assignment
from app.routes import profile as profile_routes
router.include_router(profile_routes.router)
