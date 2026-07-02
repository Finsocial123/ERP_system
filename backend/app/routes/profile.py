from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, or_
from app.core.database import get_async_db
from app.core.cloudinary_upload import upload_teacher_profile_photo_to_cloudinary
from app.dependencies.auth import get_current_user
from app.dependencies.academic_session import selected_academic_session
from app.models.academic import AcademicSession, SchoolClass, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.profile import ProfileResponse, ProfileUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.async_query import async_query
from app.core.sections import parse_section_names
router = APIRouter(prefix='/profile', tags=['Profile'])
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
ALLOWED_PROFILE_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
ALLOWED_PROFILE_PHOTO_MIME_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
MAX_PROFILE_PHOTO_BYTES = 3 * 1024 * 1024
SELF_EDIT_FIELDS = {UserRole.SUPER_ADMIN.value: ['full_name', 'email', 'phone'], UserRole.SCHOOL_OWNER.value: ['full_name', 'email', 'phone'], UserRole.SCHOOL_ADMIN.value: ['full_name', 'email', 'phone'], UserRole.TEACHER.value: ['phone', 'address'], UserRole.STUDENT.value: ['phone', 'address', 'photo_url'], UserRole.PARENT.value: ['phone', 'alternate_phone', 'occupation', 'address']}

def _clean(value: Any) -> Any:
    if value == '':
        return None
    return value

def _full_student_name(student: Student) -> str:
    return ' '.join((part for part in [student.first_name, student.last_name] if part)).strip()

def _school_payload(school: School | None) -> dict[str, Any] | None:
    if not school:
        return None
    return {'id': school.id, 'name': school.name, 'school_code': school.school_code, 'institution_type': school.institution_type, 'email': school.email, 'phone': school.phone, 'address': school.address, 'city': school.city, 'state': school.state, 'country': school.country, 'logo_url': school.logo_url}

def _account_payload(user: User) -> dict[str, Any]:
    return {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'phone': user.phone, 'login_id': user.login_id, 'role': user.role}

def _session_scoped_query(query, model, session_id: int | None):
    if session_id is not None and hasattr(model, 'academic_session_id'):
        return query.filter(model.academic_session_id == session_id)
    return query

async def _maps(db: AsyncSession, school_id: int, session_id: int | None = None) -> dict[str, dict[int, Any]]:
    class_query = _session_scoped_query(async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id), SchoolClass, session_id)
    subject_query = _session_scoped_query(async_query(db, Subject).filter(Subject.school_id == school_id), Subject, session_id)
    teacher_query = _session_scoped_query(async_query(db, Teacher).filter(Teacher.school_id == school_id), Teacher, session_id)
    classes = await class_query.all()
    subjects = await subject_query.all()
    teachers = await teacher_query.all()
    sessions = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).all()
    return {'classes': {item.id: item for item in classes}, 'sections': {}, 'subjects': {item.id: item for item in subjects}, 'teachers': {item.id: item for item in teachers}, 'sessions': {item.id: item for item in sessions}}

def _class_name(class_id: int | None, maps: dict[str, dict[int, Any]]) -> str | None:
    item = maps['classes'].get(class_id or 0)
    return item.name if item else None

def _section_name(section_id: int | None, maps: dict[str, dict[int, Any]]) -> str | None:
    if section_id is None:
        return None
    item = maps['sections'].get(section_id)
    return item.name if item else None

def _subject_name(subject_id: int | None, maps: dict[str, dict[int, Any]]) -> str | None:
    item = maps['subjects'].get(subject_id or 0)
    return item.name if item else None

def _teacher_name(teacher_id: int | None, maps: dict[str, dict[int, Any]]) -> str | None:
    item = maps['teachers'].get(teacher_id or 0)
    return item.full_name if item else None

def _student_payload(student: Student, maps: dict[str, dict[int, Any]]) -> dict[str, Any]:
    return {'id': student.id, 'name': _full_student_name(student), 'admission_no': student.admission_no, 'roll_number': student.roll_number, 'email': student.email, 'phone': student.phone, 'class_id': student.class_id, 'class_name': _class_name(student.class_id, maps), 'section_id': student.section_id, 'section_name': student.section_name, 'status': student.status, 'is_active': student.is_active}

def _teacher_payload(teacher: Teacher, maps: dict[str, dict[int, Any]] | None=None) -> dict[str, Any]:
    return {'id': teacher.id, 'name': teacher.full_name, 'employee_id': teacher.employee_id, 'email': teacher.email, 'phone': teacher.phone, 'department_id': teacher.department_id, 'photo_url': teacher.photo_url, 'status': teacher.status, 'is_active': teacher.is_active}

def _guardian_payload(guardian: ParentGuardian) -> dict[str, Any]:
    return {'id': guardian.id, 'full_name': guardian.full_name, 'relation': guardian.relation, 'email': guardian.email, 'phone': guardian.phone, 'alternate_phone': guardian.alternate_phone, 'occupation': guardian.occupation, 'address': guardian.address, 'user_id': guardian.user_id}


def _student_eager_options():
    """Relationships used by profile responses must be loaded explicitly.

    Async SQLAlchemy cannot run implicit lazy database IO when code touches
    attributes such as student.guardian. Without this, the profile page can
    raise MissingGreenlet after moving to asyncpg/Supabase.
    """
    return (
        selectinload(Student.guardian),
        selectinload(Student.school_class),
    )


async def _find_student_for_user(db: AsyncSession, user: User, session_id: int | None = None) -> Student | None:
    if not user.school_id:
        return None
    query = _session_scoped_query(async_query(db, Student).options(*_student_eager_options()).filter(Student.school_id == user.school_id, Student.user_id == user.id), Student, session_id)
    student = await query.first()
    if student:
        return student
    identifiers = {item for item in [user.email, user.login_id] if item}
    if not identifiers:
        return None
    query = _session_scoped_query(async_query(db, Student).options(*_student_eager_options()).filter(Student.school_id == user.school_id, Student.email.in_(identifiers)), Student, session_id)
    matches = await query.limit(2).all()
    return matches[0] if len(matches) == 1 else None

async def _find_teacher_for_user(db: AsyncSession, user: User, session_id: int | None = None) -> Teacher | None:
    if not user.school_id:
        return None
    query = _session_scoped_query(async_query(db, Teacher).filter(Teacher.school_id == user.school_id, Teacher.user_id == user.id), Teacher, session_id)
    teacher = await query.first()
    if teacher:
        return teacher
    identifiers = {item for item in [user.email, user.login_id] if item}
    if not identifiers:
        return None
    query = _session_scoped_query(async_query(db, Teacher).filter(Teacher.school_id == user.school_id, Teacher.email.in_(identifiers)), Teacher, session_id)
    matches = await query.limit(2).all()
    return matches[0] if len(matches) == 1 else None

def _parent_identifiers(user: User) -> set[str]:
    return {str(item).strip().lower() for item in (user.email, user.login_id) if item and str(item).strip()}

async def _find_parent_guardians_for_user(db: AsyncSession, user: User) -> list[ParentGuardian]:
    """Return only guardian records that safely belong to this parent login.

    Priority:
    1. guardian.user_id + matching guardian email/login identifier.
    2. a single user_id-linked guardian with no email.
    3. exact guardian email/login match.

    Phone matching is intentionally blocked because repeated demo numbers like
    1234567890 can make every parent see every child. If old data accidentally
    linked many guardians to one parent user, mismatched guardian emails are
    ignored to avoid data leakage.
    """
    if not user.school_id:
        return []
    identifiers = _parent_identifiers(user)
    linked = await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == user.school_id, ParentGuardian.user_id == user.id, ParentGuardian.is_active.is_(True)).order_by(ParentGuardian.id.asc()).all()
    if linked:
        email_matched = [guardian for guardian in linked if guardian.email and guardian.email.strip().lower() in identifiers]
        if email_matched:
            return email_matched
        no_email_linked = [guardian for guardian in linked if not guardian.email]
        if len(linked) == 1 and no_email_linked:
            return linked
        return []
    if not identifiers:
        return []
    return await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == user.school_id, ParentGuardian.is_active.is_(True), func.lower(ParentGuardian.email).in_(identifiers)).order_by(ParentGuardian.id.asc()).all()

async def _class_teacher_items(db: AsyncSession, school_id: int, class_id: int | None, section_id: int | None, maps: dict[str, dict[int, Any]], session_id: int | None = None, section_name: str | None = None) -> list[dict[str, Any]]:
    if class_id is None:
        return []
    query = async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.class_id == class_id, or_(ClassTeacherAssignment.section_name == section_name, ClassTeacherAssignment.section_name.is_(None)))
    query = _session_scoped_query(query, ClassTeacherAssignment, session_id)
    items = []
    for row in await query.order_by(ClassTeacherAssignment.id.asc()).all():
        session = maps['sessions'].get(row.academic_session_id or 0)
        items.append({'id': row.id, 'teacher_id': row.teacher_id, 'teacher_name': _teacher_name(row.teacher_id, maps), 'class_id': row.class_id, 'class_name': _class_name(row.class_id, maps), 'section_id': row.section_id, 'section_name': row.section_name or 'All Sections', 'academic_session_id': row.academic_session_id, 'academic_session_name': session.name if session else None})
    return items

async def _subject_teacher_items(db: AsyncSession, school_id: int, class_id: int | None, section_id: int | None, maps: dict[str, dict[int, Any]], session_id: int | None = None, section_name: str | None = None) -> list[dict[str, Any]]:
    if class_id is None:
        return []
    query = async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.class_id == class_id, or_(TeacherSubject.section_name == section_name, TeacherSubject.section_name.is_(None)))
    query = _session_scoped_query(query, TeacherSubject, session_id)
    items = []
    for row in await query.order_by(TeacherSubject.id.asc()).all():
        items.append({'id': row.id, 'teacher_id': row.teacher_id, 'teacher_name': _teacher_name(row.teacher_id, maps), 'subject_id': row.subject_id, 'subject_name': _subject_name(row.subject_id, maps), 'class_id': row.class_id, 'class_name': _class_name(row.class_id, maps), 'section_id': row.section_id, 'section_name': row.section_name or 'All Sections'})
    return items

async def _build_student_profile(db: AsyncSession, user: User, maps: dict[str, dict[int, Any]], session_id: int | None = None) -> dict[str, Any]:
    student = await _find_student_for_user(db, user, session_id)
    if not student:
        return {'student': None, 'message': 'Student record is not linked to this login yet.'}
    guardian = student.guardian
    return {'student': {**_student_payload(student, maps), 'gender': student.gender, 'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None, 'blood_group': student.blood_group, 'photo_url': student.photo_url, 'address': student.address, 'admission_date': student.admission_date.isoformat() if student.admission_date else None}, 'guardian': _guardian_payload(guardian) if guardian else None, 'class_teachers': await _class_teacher_items(db, user.school_id, student.class_id, student.section_id, maps, session_id, student.section_name), 'subject_teachers': await _subject_teacher_items(db, user.school_id, student.class_id, student.section_id, maps, session_id, student.section_name)}

async def _build_parent_profile(db: AsyncSession, user: User, maps: dict[str, dict[int, Any]], session_id: int | None = None) -> dict[str, Any]:
    guardians = await _find_parent_guardians_for_user(db, user)
    guardian_ids = [item.id for item in guardians]
    children: list[dict[str, Any]] = []
    if guardian_ids:
        student_query = _session_scoped_query(async_query(db, Student).options(*_student_eager_options()).filter(Student.school_id == user.school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True)), Student, session_id)
        students = await student_query.order_by(Student.first_name.asc(), Student.admission_no.asc()).all()
        children = [{**_student_payload(student, maps), 'class_teachers': await _class_teacher_items(db, user.school_id, student.class_id, student.section_id, maps, session_id, student.section_name), 'subject_teachers': await _subject_teacher_items(db, user.school_id, student.class_id, student.section_id, maps, session_id, student.section_name)} for student in students]
    primary_guardian = guardians[0] if guardians else None
    return {'guardian': _guardian_payload(primary_guardian) if primary_guardian else None, 'guardians': [_guardian_payload(item) for item in guardians], 'children': children, 'children_count': len(children), 'message': None if guardians else 'No guardian record is linked to this parent login yet.'}

def _scope_key(class_id: int | None, section_name: str | None) -> tuple[int | None, str | None]:
    return (class_id, section_name)

async def _students_for_scope(db: AsyncSession, school_id: int, class_id: int | None, section_name: str | None, maps: dict[str, dict[int, Any]], session_id: int | None = None) -> list[dict[str, Any]]:
    if class_id is None:
        return []
    query = async_query(db, Student).options(*_student_eager_options()).filter(Student.school_id == school_id, Student.class_id == class_id, Student.is_active.is_(True))
    query = _session_scoped_query(query, Student, session_id)
    if section_name:
        query = query.filter(Student.section_name == section_name)
    return [_student_payload(item, maps) for item in await query.order_by(Student.first_name.asc(), Student.admission_no.asc()).all()]

async def _build_teacher_profile(db: AsyncSession, user: User, maps: dict[str, dict[int, Any]], session_id: int | None = None) -> dict[str, Any]:
    teacher = await _find_teacher_for_user(db, user, session_id)
    if not teacher:
        return {'teacher': None, 'message': 'Teacher record is not linked to this login yet.'}
    class_teacher_query = _session_scoped_query(async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == user.school_id, ClassTeacherAssignment.teacher_id == teacher.id), ClassTeacherAssignment, session_id)
    subject_query = _session_scoped_query(async_query(db, TeacherSubject).filter(TeacherSubject.school_id == user.school_id, TeacherSubject.teacher_id == teacher.id), TeacherSubject, session_id)
    class_teacher_rows = await class_teacher_query.order_by(ClassTeacherAssignment.id.asc()).all()
    subject_rows = await subject_query.order_by(TeacherSubject.id.asc()).all()
    assigned_scopes: dict[tuple[int | None, str | None], dict[str, Any]] = {}
    class_teacher_items = []
    for row in class_teacher_rows:
        session = maps['sessions'].get(row.academic_session_id or 0)
        item = {'id': row.id, 'class_id': row.class_id, 'class_name': _class_name(row.class_id, maps), 'section_id': row.section_id, 'section_name': row.section_name or 'All Sections', 'academic_session_id': row.academic_session_id, 'academic_session_name': session.name if session else None}
        class_teacher_items.append(item)
        assigned_scopes[_scope_key(row.class_id, row.section_name)] = item
    subject_items = []
    for row in subject_rows:
        item = {'id': row.id, 'subject_id': row.subject_id, 'subject_name': _subject_name(row.subject_id, maps), 'class_id': row.class_id, 'class_name': _class_name(row.class_id, maps), 'section_id': row.section_id, 'section_name': row.section_name or 'All Sections'}
        subject_items.append(item)
        if row.class_id is not None:
            assigned_scopes.setdefault(_scope_key(row.class_id, row.section_name), item)
    classes = []
    for class_id, section_name in sorted(assigned_scopes.keys(), key=lambda value: (value[0] or 0, value[1] or "")):
        students = await _students_for_scope(db, user.school_id, class_id, section_name, maps, session_id)
        classes.append({'class_id': class_id, 'class_name': _class_name(class_id, maps), 'section_id': None, 'section_name': section_name or 'All Sections', 'total_students': len(students), 'students': students})
    return {'teacher': {**_teacher_payload(teacher, maps), 'gender': teacher.gender, 'qualification': teacher.qualification, 'specialization': teacher.specialization, 'joining_date': teacher.joining_date.isoformat() if teacher.joining_date else None, 'photo_url': teacher.photo_url, 'address': teacher.address}, 'class_teacher_assignments': class_teacher_items, 'subject_assignments': subject_items, 'assigned_classes': classes}

async def _active_parent_count(db: AsyncSession, school_id: int, session_id: int | None = None) -> int:
    """Count active parent records connected to active students in one session."""
    linked_query = async_query(db, func.count(func.distinct(ParentGuardian.user_id))).join(Student, Student.guardian_id == ParentGuardian.id).join(User, User.id == ParentGuardian.user_id).filter(ParentGuardian.school_id == school_id, ParentGuardian.is_active.is_(True), ParentGuardian.user_id.isnot(None), Student.school_id == school_id, Student.is_active.is_(True), User.school_id == school_id, User.role == UserRole.PARENT.value, User.is_active.is_(True))
    unlinked_query = async_query(db, func.count(func.distinct(ParentGuardian.id))).join(Student, Student.guardian_id == ParentGuardian.id).filter(ParentGuardian.school_id == school_id, ParentGuardian.is_active.is_(True), ParentGuardian.user_id.is_(None), Student.school_id == school_id, Student.is_active.is_(True))
    if session_id is not None:
        linked_query = linked_query.filter(Student.academic_session_id == session_id)
        unlinked_query = unlinked_query.filter(Student.academic_session_id == session_id)
    linked_parent_users = await linked_query.scalar()
    unlinked_guardians = await unlinked_query.scalar()
    return int(linked_parent_users or 0) + int(unlinked_guardians or 0)

async def _build_admin_profile(db: AsyncSession, school_id: int, maps: dict[str, dict[int, Any]], session_id: int | None = None) -> dict[str, Any]:
    classes = [item for item in maps['classes'].values() if item.is_active]
    student_query = _session_scoped_query(async_query(db, Student).filter(Student.school_id == school_id, Student.is_active.is_(True)), Student, session_id)
    teacher_query = _session_scoped_query(async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True)), Teacher, session_id)
    teacher_subject_query = _session_scoped_query(async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id), TeacherSubject, session_id)
    class_teacher_query = _session_scoped_query(async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id), ClassTeacherAssignment, session_id)
    students = await student_query.order_by(Student.first_name.asc()).all()
    teachers = await teacher_query.order_by(Teacher.full_name.asc()).all()
    teacher_subjects = await teacher_subject_query.all()
    class_teachers = await class_teacher_query.all()
    sections_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for school_class in classes:
        for index, section_name in enumerate(parse_section_names(school_class.sections), start=1):
            sections_by_class[school_class.id].append({'id': index, 'name': section_name, 'is_active': True})
    students_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for student in students:
        if student.class_id is not None:
            students_by_class[student.class_id].append(_student_payload(student, maps))
    subject_teachers_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in teacher_subjects:
        if row.class_id is None:
            continue
        subject_teachers_by_class[row.class_id].append({'id': row.id, 'teacher_id': row.teacher_id, 'teacher_name': _teacher_name(row.teacher_id, maps), 'subject_id': row.subject_id, 'subject_name': _subject_name(row.subject_id, maps), 'section_id': row.section_id, 'section_name': row.section_name or 'All Sections'})
    class_teachers_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in class_teachers:
        session = maps['sessions'].get(row.academic_session_id or 0)
        class_teachers_by_class[row.class_id].append({'id': row.id, 'teacher_id': row.teacher_id, 'teacher_name': _teacher_name(row.teacher_id, maps), 'section_id': row.section_id, 'section_name': row.section_name or 'All Sections', 'academic_session_id': row.academic_session_id, 'academic_session_name': session.name if session else None})
    class_items = []
    for school_class in sorted(classes, key=lambda item: item.name):
        class_students = students_by_class.get(school_class.id, [])
        class_items.append({'id': school_class.id, 'name': school_class.name, 'code': school_class.code, 'is_active': school_class.is_active, 'total_students': len(class_students), 'sections': sections_by_class.get(school_class.id, []), 'students': class_students, 'class_teachers': class_teachers_by_class.get(school_class.id, []), 'subject_teachers': subject_teachers_by_class.get(school_class.id, [])})
    return {'classes': class_items, 'teachers': [_teacher_payload(item, maps) for item in teachers], 'subjects': [{'id': item.id, 'name': item.name, 'code': item.code, 'class_id': item.class_id, 'class_name': _class_name(item.class_id, maps), 'is_active': item.is_active} for item in maps['subjects'].values() if item.is_active]}

@router.get('', response_model=ProfileResponse)
async def get_my_profile(request: Request, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    school = await db.get(School, current_user.school_id) if current_user.school_id else None
    response: dict[str, Any] = {'account': _account_payload(current_user), 'school': _school_payload(school), 'editable_fields': SELF_EDIT_FIELDS.get(current_user.role, []), 'summary': {}, 'role_data': {}}
    if not current_user.school_id:
        return response

    session = await selected_academic_session(db, current_user.school_id, request=request, current_user=current_user)
    session_id = session.id if session else None
    response['summary'] = {
        'academic_session_id': session_id,
        'academic_session_name': session.name if session else None,
    }
    maps = await _maps(db, current_user.school_id, session_id)
    if current_user.role == UserRole.STUDENT.value:
        response['role_data'] = await _build_student_profile(db, current_user, maps, session_id)
    elif current_user.role == UserRole.TEACHER.value:
        response['role_data'] = await _build_teacher_profile(db, current_user, maps, session_id)
    elif current_user.role == UserRole.PARENT.value:
        response['role_data'] = await _build_parent_profile(db, current_user, maps, session_id)
    elif current_user.role in ADMIN_ROLES:
        response['role_data'] = await _build_admin_profile(db, current_user.school_id, maps, session_id)
        response['summary'].update({
            'students': await _session_scoped_query(async_query(db, Student).filter(Student.school_id == current_user.school_id, Student.is_active.is_(True)), Student, session_id).count(),
            'teachers': await _session_scoped_query(async_query(db, Teacher).filter(Teacher.school_id == current_user.school_id, Teacher.is_active.is_(True)), Teacher, session_id).count(),
            'parents': await _active_parent_count(db, current_user.school_id, session_id),
            'classes': await _session_scoped_query(async_query(db, SchoolClass).filter(SchoolClass.school_id == current_user.school_id, SchoolClass.is_active.is_(True)), SchoolClass, session_id).count(),
            'subjects': await _session_scoped_query(async_query(db, Subject).filter(Subject.school_id == current_user.school_id, Subject.is_active.is_(True)), Subject, session_id).count(),
        })
    return response


@router.post('/teacher/photo', response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def upload_teacher_profile_photo(request: Request, file: UploadFile=File(...), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.TEACHER.value:
        raise HTTPException(status_code=403, detail='Only teachers can upload a profile photo from this endpoint')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    session = await selected_academic_session(db, current_user.school_id, request=request, current_user=current_user)
    teacher = await _find_teacher_for_user(db, current_user, session.id if session else None)
    if not teacher:
        raise HTTPException(status_code=404, detail='Teacher record is not linked to this login yet')

    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_PROFILE_PHOTO_EXTENSIONS or file.content_type not in ALLOWED_PROFILE_PHOTO_MIME_TYPES:
        raise HTTPException(status_code=400, detail='Upload a PNG, JPG, JPEG, or WEBP profile photo')

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail='Profile photo file is empty')
    if len(content) > MAX_PROFILE_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail='Profile photo must be 3 MB or smaller')

    teacher.photo_url = await upload_teacher_profile_photo_to_cloudinary(
        school_id=current_user.school_id,
        teacher_id=teacher.id,
        content=content,
        content_type=file.content_type or 'image/png',
    )
    await db.commit()
    await db.refresh(current_user)
    return await get_my_profile(request=request, current_user=current_user, db=db)

@router.put('', response_model=ProfileResponse)
async def update_my_profile(payload: ProfileUpdate, request: Request, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    editable = set(SELF_EDIT_FIELDS.get(current_user.role, []))
    if not editable:
        raise HTTPException(status_code=403, detail='This role cannot edit profile details from here')
    data = payload.model_dump(exclude_unset=True)
    blocked = sorted(set(data.keys()) - editable)
    if blocked:
        raise HTTPException(status_code=400, detail=f"These fields cannot be edited here: {', '.join(blocked)}")
    session = await selected_academic_session(db, current_user.school_id, request=request, current_user=current_user) if current_user.school_id else None
    session_id = session.id if session else None
    if current_user.role in ADMIN_ROLES:
        if 'full_name' in data:
            current_user.full_name = _clean(data['full_name']) or current_user.full_name
        if 'email' in data:
            current_user.email = str(_clean(data['email']) or current_user.email)
        if 'phone' in data:
            current_user.phone = _clean(data['phone'])
    elif current_user.role == UserRole.STUDENT.value:
        student = await _find_student_for_user(db, current_user, session_id)
        if not student:
            raise HTTPException(status_code=404, detail='Student record is not linked to this login yet')
        if 'phone' in data:
            student.phone = _clean(data['phone'])
            current_user.phone = student.phone
        if 'address' in data:
            student.address = _clean(data['address'])
        if 'photo_url' in data:
            student.photo_url = _clean(data['photo_url'])
    elif current_user.role == UserRole.TEACHER.value:
        teacher = await _find_teacher_for_user(db, current_user, session_id)
        if not teacher:
            raise HTTPException(status_code=404, detail='Teacher record is not linked to this login yet')
        if 'phone' in data:
            teacher.phone = _clean(data['phone'])
            current_user.phone = teacher.phone
        if 'address' in data:
            teacher.address = _clean(data['address'])
        if 'photo_url' in data:
            teacher.photo_url = _clean(data['photo_url'])
    elif current_user.role == UserRole.PARENT.value:
        guardians = await _find_parent_guardians_for_user(db, current_user)
        if not guardians:
            raise HTTPException(status_code=404, detail='Guardian record is not linked to this login yet')
        for guardian in guardians:
            if 'phone' in data:
                guardian.phone = _clean(data['phone'])
            if 'alternate_phone' in data:
                guardian.alternate_phone = _clean(data['alternate_phone'])
            if 'occupation' in data:
                guardian.occupation = _clean(data['occupation'])
            if 'address' in data:
                guardian.address = _clean(data['address'])
        if 'phone' in data:
            current_user.phone = _clean(data['phone'])
    await db.commit()
    await db.refresh(current_user)
    return await get_my_profile(request=request, current_user=current_user, db=db)
