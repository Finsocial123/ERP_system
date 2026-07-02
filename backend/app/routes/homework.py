from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import inspect, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.core.database import get_async_db
from app.dependencies.academic_session import selected_academic_session, require_writable_academic_session, writable_selected_academic_session, assert_item_session_is_writable
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Subject
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.user import User, UserRole
from app.utils.parent_scope import children_for_parent
from app.schemas.common import MessageResponse
from app.schemas.homework import HomeworkAssignmentRead, HomeworkCheckPayload, HomeworkMetaItem, HomeworkMetaResponse, HomeworkSubmissionRead, HomeworkStats, ParentHomeworkRead, StudentHomeworkRead
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
from app.core.sections import class_section_options, validate_class_section_name
from app.services.notification_service import (
    format_date,
    notify_student_record,
    notify_student_scope,
    notify_teacher_record,
)
router = APIRouter(prefix='/homework', tags=['Phase 5 - Homework and Assignment'], dependencies=[Depends(require_writable_academic_session)])
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
MANAGER_ROLES = [UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER]
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / 'uploads'
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif'}

def _full_student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name or ''}".strip()

async def _current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    active = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True)).order_by(AcademicSession.id.desc()).first()
    if active:
        return active
    return await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()

async def _teacher_for_user(db: AsyncSession, school_id: int, user: User, session_id: int | None = None) -> Teacher | None:
    query = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.user_id == user.id)
    if session_id is not None:
        query = query.filter(Teacher.academic_session_id == session_id)
    teacher = await query.first()
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
    query = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True), or_(*conditions))
    if session_id is not None:
        query = query.filter(Teacher.academic_session_id == session_id)
    return await query.first()

async def _student_for_user(db: AsyncSession, school_id: int, user: User, session_id: int | None = None) -> Student | None:
    query = async_query(db, Student).filter(Student.school_id == school_id, Student.user_id == user.id)
    if session_id is not None:
        query = query.filter(Student.academic_session_id == session_id)
    student = await query.first()
    if student:
        return student
    conditions = []
    if user.email:
        conditions.append(Student.email == user.email)
    if user.phone:
        conditions.append(Student.phone == user.phone)
    if user.login_id:
        conditions.append(Student.admission_no == user.login_id)
    if not conditions:
        return None
    query = async_query(db, Student).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(*conditions))
    if session_id is not None:
        query = query.filter(Student.academic_session_id == session_id)
    return await query.first()

async def _children_for_parent(db: AsyncSession, school_id: int, user: User, session_id: int | None = None) -> list[Student]:
    children = await children_for_parent(db, school_id, user)
    if session_id is None:
        return children
    return [child for child in children if child.academic_session_id == session_id]

async def _validate_same_school(db: AsyncSession, model, item_id: int | None, school_id: int, field_name: str):
    if item_id is None:
        return None
    item = await async_query(db, model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f'{field_name} not found for this school')
    return item

async def _validate_assignment_scope(db: AsyncSession, school_id: int, class_id: int, section_id: int | None, section_name: str | None, subject_id: int | None, session_id: int | None = None):
    school_class = await _validate_same_school(db, SchoolClass, class_id, school_id, 'Class')
    resolved_section_name = await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id, session_id=session_id)
    subject = await _validate_same_school(db, Subject, subject_id, school_id, 'Subject')
    if subject and subject.class_id != class_id:
        raise HTTPException(status_code=400, detail='Selected subject does not belong to selected class')
    return (school_class, resolved_section_name, subject)

def _parse_form_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail='Due date must be in YYYY-MM-DD format')

def _student_query_for_assignment(db: AsyncSession, assignment: HomeworkAssignment):
    query = async_query(db, Student).filter(Student.school_id == assignment.school_id, Student.class_id == assignment.class_id, Student.is_active.is_(True))
    if assignment.academic_session_id is not None:
        query = query.filter(Student.academic_session_id == assignment.academic_session_id)
    if assignment.section_name:
        query = query.filter(Student.section_name == assignment.section_name)
    elif assignment.section_id is not None:
        query = query.filter(Student.section_id == assignment.section_id)
    return query.order_by(Student.roll_number.asc(), Student.first_name.asc())

async def _assignment_stats(db: AsyncSession, assignment: HomeworkAssignment) -> HomeworkStats:
    total_students = await _student_query_for_assignment(db, assignment).count()
    from sqlalchemy import case, func as _func
    counts = await async_query(db, _func.count(HomeworkSubmission.id).label('total'), _func.sum(case((HomeworkSubmission.status == 'SUBMITTED', 1), else_=0)).label('submitted'), _func.sum(case((HomeworkSubmission.status == 'CHECKED', 1), else_=0)).label('checked')).filter(HomeworkSubmission.school_id == assignment.school_id, HomeworkSubmission.homework_id == assignment.id).first()
    submitted = int(counts.submitted or 0)
    checked = int(counts.checked or 0)
    pending = max(total_students - submitted - checked, 0)
    return HomeworkStats(total_students=total_students, pending=pending, submitted=submitted, checked=checked)

async def _assignment_payload(db: AsyncSession, assignment: HomeworkAssignment) -> HomeworkAssignmentRead:
    """Build the API payload without triggering async lazy-loads.

    AsyncSession cannot run relationship lazy-loading from normal attribute access
    (for example assignment.school_class.name). If the relationship was eagerly
    loaded, reuse it. Otherwise fetch the display names explicitly with awaited
    queries. This prevents sqlalchemy.exc.MissingGreenlet after create/update/submit.
    """
    unloaded = inspect(assignment).unloaded

    class_name = None
    if 'school_class' not in unloaded:
        class_name = assignment.school_class.name if assignment.school_class else None
    else:
        school_class = await async_query(db, SchoolClass).filter(
            SchoolClass.id == assignment.class_id,
            SchoolClass.school_id == assignment.school_id,
        ).first()
        class_name = school_class.name if school_class else None

    section_name = assignment.section_name

    subject_name = None
    if assignment.subject_id is not None:
        if 'subject' not in unloaded:
            subject_name = assignment.subject.name if assignment.subject else None
        else:
            subject = await async_query(db, Subject).filter(
                Subject.id == assignment.subject_id,
                Subject.school_id == assignment.school_id,
            ).first()
            subject_name = subject.name if subject else None

    teacher_name = None
    if assignment.teacher_id is not None:
        if 'teacher' not in unloaded:
            teacher_name = assignment.teacher.full_name if assignment.teacher else None
        else:
            teacher = await async_query(db, Teacher).filter(
                Teacher.id == assignment.teacher_id,
                Teacher.school_id == assignment.school_id,
            ).first()
            teacher_name = teacher.full_name if teacher else None

    return HomeworkAssignmentRead(
        id=assignment.id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        class_id=assignment.class_id,
        section_id=assignment.section_id,
        subject_id=assignment.subject_id,
        teacher_id=assignment.teacher_id,
        academic_session_id=assignment.academic_session_id,
        class_name=class_name,
        section_name=section_name,
        subject_name=subject_name,
        teacher_name=teacher_name,
        attachment_url=assignment.attachment_url,
        attachment_filename=assignment.attachment_filename,
        is_active=assignment.is_active,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        stats=await _assignment_stats(db, assignment),
    )

async def _student_homework_payload(db: AsyncSession, assignment: HomeworkAssignment, student: Student) -> StudentHomeworkRead:
    submission = await async_query(db, HomeworkSubmission).filter(HomeworkSubmission.school_id == assignment.school_id, HomeworkSubmission.homework_id == assignment.id, HomeworkSubmission.student_id == student.id).first()
    base = (await _assignment_payload(db, assignment)).model_dump()
    return StudentHomeworkRead(**base, submission_id=submission.id if submission else None, submission_status=submission.status if submission else 'PENDING', submitted_at=submission.created_at if submission else None, answer_text=submission.answer_text if submission else None, submission_attachment_url=submission.attachment_url if submission else None, submission_attachment_filename=submission.attachment_filename if submission else None, teacher_feedback=submission.teacher_feedback if submission else None, checked_at=submission.checked_at if submission else None)

async def _can_manage_assignment(db: AsyncSession, school_id: int, user: User, assignment: HomeworkAssignment) -> bool:
    if user.role in ADMIN_ROLES:
        return True
    if user.role != UserRole.TEACHER.value:
        return False
    teacher = await _teacher_for_user(db, school_id, user, assignment.academic_session_id)
    return bool(teacher and assignment.teacher_id == teacher.id)

async def _get_assignment_or_404(db: AsyncSession, school_id: int, assignment_id: int) -> HomeworkAssignment:
    assignment = await async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.id == assignment_id, HomeworkAssignment.is_active.is_(True)).first()
    if not assignment:
        raise HTTPException(status_code=404, detail='Homework assignment not found')
    return assignment

def _is_assignment_for_student(assignment: HomeworkAssignment, student: Student) -> bool:
    if assignment.school_id != student.school_id or assignment.class_id != student.class_id:
        return False
    if assignment.academic_session_id is not None and student.academic_session_id != assignment.academic_session_id:
        return False
    if assignment.section_name:
        return (student.section_name or "").casefold() == assignment.section_name.casefold()
    return assignment.section_id is None or assignment.section_id == student.section_id

async def _save_upload(file: UploadFile | None, folder: str) -> tuple[str | None, str | None]:
    if file is None or not file.filename:
        return (None, None)
    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix.lower()
    content_type = file.content_type or ''
    if content_type in ALLOWED_UPLOAD_TYPES:
        suffix = ALLOWED_UPLOAD_TYPES[content_type]
    elif suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail='Only PDF and image files are allowed')
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail='File is too large. Maximum allowed size is 10 MB')
    target_dir = UPLOAD_ROOT / 'homework' / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f'{uuid4().hex}{suffix}'
    target_path = target_dir / stored_name
    target_path.write_bytes(data)
    return (f'/uploads/homework/{folder}/{stored_name}', original_name)

async def _teacher_scope_hint(db: AsyncSession, school_id: int, teacher: Teacher | None, session_id: int | None = None) -> set[tuple[int | None, int | None]]:
    if not teacher:
        return set()
    scopes: set[tuple[int | None, int | None]] = set()
    ts_query = async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id)
    ct_query = async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id)
    if session_id is not None:
        ts_query = ts_query.filter(TeacherSubject.academic_session_id == session_id)
        ct_query = ct_query.filter(ClassTeacherAssignment.academic_session_id == session_id)
    for item in await ts_query.all():
        scopes.add((item.class_id, item.section_id))
    for item in await ct_query.all():
        scopes.add((item.class_id, item.section_id))
    return scopes

@router.get('/meta', response_model=HomeworkMetaResponse)
async def homework_meta(request: Request, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request=request, current_user=current_user)
    session_id = session.id if session else None
    class_query = async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True))
    subject_query = async_query(db, Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True))
    if session_id is not None:
        class_query = class_query.filter(SchoolClass.academic_session_id == session_id)
        subject_query = subject_query.filter(Subject.academic_session_id == session_id)
    class_query = class_query.order_by(SchoolClass.name.asc())
    subject_query = subject_query.order_by(Subject.name.asc())
    if current_user.role == UserRole.TEACHER.value:
        teacher = await _teacher_for_user(db, school_id, current_user, session.id if session else None)
        scopes = await _teacher_scope_hint(db, school_id, teacher, session_id)
        class_ids = {class_id for class_id, _ in scopes if class_id is not None}
        if class_ids:
            class_query = class_query.filter(SchoolClass.id.in_(class_ids))
            subject_query = subject_query.filter(Subject.class_id.in_(class_ids))
    teacher_query = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True))
    if session_id is not None:
        teacher_query = teacher_query.filter(Teacher.academic_session_id == session_id)
    teachers = await teacher_query.order_by(Teacher.full_name.asc()).all()
    return HomeworkMetaResponse(classes=[HomeworkMetaItem(id=item.id, name=item.name, extra=item.code) for item in await class_query.all()], sections=[HomeworkMetaItem(id=item.id, name=item.name, extra=item.extra) for item in await class_section_options(db, school_id, session_id=session_id)], subjects=[HomeworkMetaItem(id=item.id, name=item.name, extra=str(item.class_id)) for item in await subject_query.all()], teachers=[HomeworkMetaItem(id=item.id, name=item.full_name, extra=item.employee_id) for item in teachers], current_academic_session_id=session.id if session else None)

@router.get('/assignments', response_model=list[HomeworkAssignmentRead])
async def list_assignments(request: Request, class_id: int | None=Query(default=None), section_id: int | None=Query(default=None), subject_id: int | None=Query(default=None), search: str | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request=request, current_user=current_user)
    session_id = session.id if session else None
    query = async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.is_active.is_(True))
    if session_id is not None:
        query = query.filter(HomeworkAssignment.academic_session_id == session_id)
    if current_user.role == UserRole.TEACHER.value:
        teacher = await _teacher_for_user(db, school_id, current_user, session.id if session else None)
        if not teacher:
            return []
        query = query.filter(HomeworkAssignment.teacher_id == teacher.id)
    if class_id is not None:
        query = query.filter(HomeworkAssignment.class_id == class_id)
    if section_id is not None and class_id is not None:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session_id)
        query = query.filter(HomeworkAssignment.section_name == section_name)
    elif section_id is not None:
        query = query.filter(HomeworkAssignment.section_id == section_id)
    if subject_id is not None:
        query = query.filter(HomeworkAssignment.subject_id == subject_id)
    if search:
        like = f'%{search.strip()}%'
        query = query.filter(or_(HomeworkAssignment.title.ilike(like), HomeworkAssignment.description.ilike(like)))
    assignments = await query.options(joinedload(HomeworkAssignment.school_class), joinedload(HomeworkAssignment.subject), joinedload(HomeworkAssignment.teacher)).order_by(HomeworkAssignment.created_at.desc()).all()
    return [await _assignment_payload(db, assignment) for assignment in assignments]

@router.post('/assignments', response_model=HomeworkAssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(request: Request, title: str=Form(..., min_length=2, max_length=180), description: str | None=Form(default=None), due_date: str=Form(...), class_id: int=Form(...), section_id: int | None=Form(default=None), section_name: str | None=Form(default=None), subject_id: int | None=Form(default=None), teacher_id: int | None=Form(default=None), attachment: UploadFile | None=File(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    parsed_due_date = _parse_form_date(due_date)
    session = await writable_selected_academic_session(db, school_id, request=request, current_user=current_user)
    _, resolved_section_name, _ = await _validate_assignment_scope(db, school_id, class_id, section_id, section_name, subject_id, session.id if session else None)
    assigned_teacher_id = teacher_id
    if current_user.role == UserRole.TEACHER.value:
        teacher = await _teacher_for_user(db, school_id, current_user, session.id if session else None)
        if not teacher:
            raise HTTPException(status_code=403, detail='Teacher profile not found for this login')
        assigned_teacher_id = teacher.id
    elif assigned_teacher_id is not None:
        await _validate_same_school(db, Teacher, assigned_teacher_id, school_id, 'Teacher')
    attachment_url, attachment_filename = await _save_upload(attachment, 'assignments')
    assignment = HomeworkAssignment(school_id=school_id, teacher_id=assigned_teacher_id, class_id=class_id, section_id=None, section_name=resolved_section_name, subject_id=subject_id, academic_session_id=session.id if session else None, title=title.strip(), description=description.strip() if description else None, due_date=parsed_due_date, attachment_url=attachment_url, attachment_filename=attachment_filename)
    db.add(assignment)
    await db.flush()
    await notify_student_scope(
        db,
        school_id=school_id,
        class_id=assignment.class_id,
        section_id=assignment.section_id,
        academic_session_id=assignment.academic_session_id,
        title='New homework assigned',
        message=f"{assignment.title} is due on {format_date(assignment.due_date)}.",
        category='HOMEWORK',
        priority='NORMAL',
        created_by=current_user.id,
        student_link='/student-homework',
        parent_link='/parent-homework',
    )
    await db.commit()
    await db.refresh(assignment)
    return await _assignment_payload(db, assignment)

@router.put('/assignments/{assignment_id}', response_model=HomeworkAssignmentRead)
async def update_assignment(assignment_id: int, title: str=Form(..., min_length=2, max_length=180), description: str | None=Form(default=None), due_date: str=Form(...), class_id: int=Form(...), section_id: int | None=Form(default=None), section_name: str | None=Form(default=None), subject_id: int | None=Form(default=None), attachment: UploadFile | None=File(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    assignment = await _get_assignment_or_404(db, school_id, assignment_id)
    await assert_item_session_is_writable(db, school_id, assignment)
    if not await _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail='You can update only your own homework')
    _, resolved_section_name, _ = await _validate_assignment_scope(db, school_id, class_id, section_id, section_name, subject_id, assignment.academic_session_id)
    assignment.title = title.strip()
    assignment.description = description.strip() if description else None
    assignment.due_date = _parse_form_date(due_date)
    assignment.class_id = class_id
    assignment.section_id = None
    assignment.section_name = resolved_section_name
    assignment.subject_id = subject_id
    attachment_url, attachment_filename = await _save_upload(attachment, 'assignments')
    if attachment_url:
        assignment.attachment_url = attachment_url
        assignment.attachment_filename = attachment_filename
    await notify_student_scope(
        db,
        school_id=school_id,
        class_id=assignment.class_id,
        section_id=assignment.section_id,
        academic_session_id=assignment.academic_session_id,
        title='Homework updated',
        message=f"{assignment.title} was updated. Due date: {format_date(assignment.due_date)}.",
        category='HOMEWORK',
        priority='NORMAL',
        created_by=current_user.id,
        student_link='/student-homework',
        parent_link='/parent-homework',
    )
    await db.commit()
    await db.refresh(assignment)
    return await _assignment_payload(db, assignment)

@router.delete('/assignments/{assignment_id}', response_model=MessageResponse)
async def delete_assignment(assignment_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    assignment = await _get_assignment_or_404(db, school_id, assignment_id)
    await assert_item_session_is_writable(db, school_id, assignment)
    if not await _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail='You can delete only your own homework')
    assignment.is_active = False
    await db.commit()
    return {'message': 'Homework assignment deleted'}

@router.get('/assignments/{assignment_id}/submissions', response_model=list[HomeworkSubmissionRead])
async def list_assignment_submissions(assignment_id: int, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    assignment = await _get_assignment_or_404(db, school_id, assignment_id)
    if not await _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail='You can view submissions only for your own homework')
    submissions = {item.student_id: item for item in await async_query(db, HomeworkSubmission).filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.homework_id == assignment_id).all()}
    rows: list[HomeworkSubmissionRead] = []
    for student in await _student_query_for_assignment(db, assignment).all():
        submission = submissions.get(student.id)
        rows.append(HomeworkSubmissionRead(id=submission.id if submission else None, homework_id=assignment.id, student_id=student.id, student_name=_full_student_name(student), admission_no=student.admission_no, roll_number=student.roll_number, status=submission.status if submission else 'PENDING', answer_text=submission.answer_text if submission else None, attachment_url=submission.attachment_url if submission else None, attachment_filename=submission.attachment_filename if submission else None, teacher_feedback=submission.teacher_feedback if submission else None, submitted_at=submission.created_at if submission else None, checked_at=submission.checked_at if submission else None))
    return rows

@router.get('/student/assignments', response_model=list[StudentHomeworkRead])
async def list_student_homework(request: Request, status_filter: str | None=Query(default=None, alias='status'), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.STUDENT)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request=request, current_user=current_user)
    session_id = session.id if session else None
    student = await _student_for_user(db, school_id, current_user, session_id)
    if not student:
        return []
    assignment_query = async_query(db, HomeworkAssignment).options(joinedload(HomeworkAssignment.school_class), joinedload(HomeworkAssignment.subject), joinedload(HomeworkAssignment.teacher)).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.class_id == student.class_id, HomeworkAssignment.is_active.is_(True), or_(HomeworkAssignment.section_name.is_(None), HomeworkAssignment.section_name == student.section_name))
    if session_id is not None:
        assignment_query = assignment_query.filter(HomeworkAssignment.academic_session_id == session_id)
    assignments = await assignment_query.order_by(HomeworkAssignment.due_date.asc(), HomeworkAssignment.created_at.desc()).all()
    assignment_ids = [a.id for a in assignments]
    submissions_map = {}
    if assignment_ids:
        submissions_map = {s.homework_id: s for s in await async_query(db, HomeworkSubmission).filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.student_id == student.id, HomeworkSubmission.homework_id.in_(assignment_ids)).all()}
    rows = []
    for assignment in assignments:
        submission = submissions_map.get(assignment.id)
        base = (await _assignment_payload(db, assignment)).model_dump()
        row = StudentHomeworkRead(**base, submission_id=submission.id if submission else None, submission_status=submission.status if submission else 'PENDING', submitted_at=submission.created_at if submission else None, answer_text=submission.answer_text if submission else None, submission_attachment_url=submission.attachment_url if submission else None, submission_attachment_filename=submission.attachment_filename if submission else None, teacher_feedback=submission.teacher_feedback if submission else None, checked_at=submission.checked_at if submission else None)
        rows.append(row)
    if status_filter:
        rows = [row for row in rows if row.submission_status == status_filter.upper()]
    return rows

@router.post('/assignments/{assignment_id}/submit', response_model=StudentHomeworkRead)
async def submit_homework(assignment_id: int, request: Request, answer_text: str | None=Form(default=None), attachment: UploadFile | None=File(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.STUDENT)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request=request, current_user=current_user)
    session_id = session.id if session else None
    student = await _student_for_user(db, school_id, current_user, session_id)
    if not student:
        raise HTTPException(status_code=404, detail='Student profile not found for this login')
    assignment = await _get_assignment_or_404(db, school_id, assignment_id)
    await assert_item_session_is_writable(db, school_id, assignment)
    if not _is_assignment_for_student(assignment, student):
        raise HTTPException(status_code=403, detail='This homework is not assigned to your class or section')
    submission = await async_query(db, HomeworkSubmission).filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.homework_id == assignment_id, HomeworkSubmission.student_id == student.id).first()
    if not submission:
        submission = HomeworkSubmission(school_id=school_id, homework_id=assignment_id, student_id=student.id)
        db.add(submission)
    attachment_url, attachment_filename = await _save_upload(attachment, 'submissions')
    submission.answer_text = answer_text.strip() if answer_text else None
    submission.status = 'SUBMITTED'
    submission.teacher_feedback = None
    submission.checked_at = None
    if attachment_url:
        submission.attachment_url = attachment_url
        submission.attachment_filename = attachment_filename
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail='Homework already submitted. Refresh and try again')
    await notify_teacher_record(
        db,
        school_id=school_id,
        teacher_id=assignment.teacher_id,
        title='Homework submitted',
        message=f"{_full_student_name(student)} submitted {assignment.title}.",
        category='HOMEWORK',
        priority='NORMAL',
        created_by=current_user.id,
        link='/teacher-homework',
    )
    await db.commit()
    await db.refresh(assignment)
    return await _student_homework_payload(db, assignment, student)

@router.patch('/submissions/{submission_id}/check', response_model=HomeworkSubmissionRead)
async def check_submission(submission_id: int, payload: HomeworkCheckPayload, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*MANAGER_ROLES)), db: AsyncSession=Depends(get_async_db)):
    submission = await async_query(db, HomeworkSubmission).filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail='Submission not found')
    assignment = await async_query(db, HomeworkAssignment).filter(
        HomeworkAssignment.school_id == school_id,
        HomeworkAssignment.id == submission.homework_id,
    ).first()
    if assignment:
        await assert_item_session_is_writable(db, school_id, assignment)
    if not assignment or not await _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail='You can check submissions only for your own homework')
    student = await async_query(db, Student).filter(
        Student.school_id == school_id,
        Student.id == submission.student_id,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found for this submission')
    submission.status = 'CHECKED'
    submission.teacher_feedback = payload.teacher_feedback
    submission.checked_at = datetime.utcnow()
    await notify_student_record(
        db,
        school_id=school_id,
        student=student,
        title='Homework checked',
        message=f"Your submission for {assignment.title} has been checked.",
        category='HOMEWORK',
        priority='NORMAL',
        created_by=current_user.id,
        student_link='/student-homework',
        parent_link='/parent-homework',
    )
    await db.commit()
    await db.refresh(submission)
    return HomeworkSubmissionRead(id=submission.id, homework_id=submission.homework_id, student_id=submission.student_id, student_name=_full_student_name(student), admission_no=student.admission_no, roll_number=student.roll_number, status=submission.status, answer_text=submission.answer_text, attachment_url=submission.attachment_url, attachment_filename=submission.attachment_filename, teacher_feedback=submission.teacher_feedback, submitted_at=submission.created_at, checked_at=submission.checked_at)

@router.get('/parent/assignments', response_model=list[ParentHomeworkRead])
async def list_parent_homework(request: Request, child_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(UserRole.PARENT)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request=request, current_user=current_user)
    session_id = session.id if session else None
    children = await _children_for_parent(db, school_id, current_user, session_id)
    if child_id is not None:
        children = [child for child in children if child.id == child_id]
    rows: list[ParentHomeworkRead] = []
    for child in children:
        assignment_query = async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.class_id == child.class_id, HomeworkAssignment.is_active.is_(True), or_(HomeworkAssignment.section_name.is_(None), HomeworkAssignment.section_name == child.section_name))
        if session_id is not None:
            assignment_query = assignment_query.filter(HomeworkAssignment.academic_session_id == session_id)
        assignments = await assignment_query.order_by(HomeworkAssignment.due_date.asc(), HomeworkAssignment.created_at.desc()).all()
        for assignment in assignments:
            payload = (await _student_homework_payload(db, assignment, child)).model_dump()
            rows.append(ParentHomeworkRead(**payload, student_id=child.id, student_name=_full_student_name(child), admission_no=child.admission_no))
    return rows
