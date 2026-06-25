from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.dependencies.academic_session import selected_academic_session, require_writable_academic_session, writable_selected_academic_session, assert_item_session_is_writable
from app.models.academic import AcademicSession, SchoolClass
from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher
from app.models.user import User, UserRole
from app.schemas.attendance import AttendanceRead, AttendanceUpdate, BulkAttendanceCreate, DayAttendanceRecord, StudentAttendanceSummary
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
from app.core.sections import validate_class_section_name
from app.services.notification_service import format_date, notify_student_record
router = APIRouter(prefix='/attendance', tags=['Phase 4 - Attendance'], dependencies=[Depends(require_writable_academic_session)])
ADMIN_ROLES = [UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN]
ALLOWED_ROLES = [*ADMIN_ROLES, UserRole.TEACHER]
TEACHER_ROLE_VALUE = UserRole.TEACHER.value

async def _validate_session(db: AsyncSession, session_id: int, school_id: int) -> AcademicSession:
    sess = await async_query(db, AcademicSession).filter(AcademicSession.id == session_id, AcademicSession.school_id == school_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail='Academic session not found')
    return sess

async def _validate_class(db: AsyncSession, class_id: int, school_id: int) -> SchoolClass:
    cls = await async_query(db, SchoolClass).filter(SchoolClass.id == class_id, SchoolClass.school_id == school_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail='Class not found')
    return cls

def _student_full_name(s: Student) -> str:
    return f"{s.first_name} {s.last_name or ''}".strip()

def _is_teacher(user: User) -> bool:
    """Check if the user's role is TEACHER (compares string value, not enum)."""
    return user.role == TEACHER_ROLE_VALUE

async def _get_teacher(db: AsyncSession, school_id: int, user: User, academic_session_id: int | None=None) -> Teacher | None:
    """Resolve the Teacher record for the logged-in user."""
    query = async_query(db, Teacher).filter(Teacher.user_id == user.id, Teacher.school_id == school_id)
    if academic_session_id is not None:
        query = query.filter(Teacher.academic_session_id == academic_session_id)
    return await query.first()

async def _teacher_allowed_class_ids(db: AsyncSession, school_id: int, teacher: Teacher, academic_session_id: int | None=None) -> set[int]:
    """
    Return the set of class_ids a teacher is allowed to take attendance for.
    ONLY ClassTeacherAssignment is used — a teacher must be assigned as the
    class teacher of a class. Subject teacher assignment does NOT grant access.
    """
    query = async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.teacher_id == teacher.id, ClassTeacherAssignment.school_id == school_id)
    if academic_session_id is not None:
        query = query.filter(ClassTeacherAssignment.academic_session_id == academic_session_id)
    return {row.class_id for row in await query.all()}

async def _assert_teacher_can_access_class(db: AsyncSession, school_id: int, user: User, class_id: int, academic_session_id: int | None=None) -> None:
    """
    Raise 403 if a TEACHER tries to access a class they are not assigned to.
    Admin roles pass through unconditionally.
    """
    if not _is_teacher(user):
        return
    teacher = await _get_teacher(db, school_id, user, academic_session_id)
    if not teacher:
        raise HTTPException(status_code=403, detail='No teacher profile found for your account. Contact admin.')
    allowed = await _teacher_allowed_class_ids(db, school_id, teacher, academic_session_id)
    if class_id not in allowed:
        raise HTTPException(status_code=403, detail='You are not assigned to this class.')

@router.get('/my-classes', response_model=list[dict])
async def teacher_allowed_classes(request: Request, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALLOWED_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user)
    session_id = session.id if session else None
    if _is_teacher(current_user):
        teacher = await _get_teacher(db, school_id, current_user, session_id)
        if not teacher:
            return []
        allowed_ids = await _teacher_allowed_class_ids(db, school_id, teacher, session_id)
        if not allowed_ids:
            return []
        classes = await async_query(db, SchoolClass).filter(SchoolClass.id.in_(allowed_ids), SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True), SchoolClass.academic_session_id == session_id).order_by(SchoolClass.name).all()
    else:
        classes = await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True), SchoolClass.academic_session_id == session_id).order_by(SchoolClass.name).all()
    return [{'id': c.id, 'name': c.name} for c in classes]

@router.post('/bulk', response_model=list[AttendanceRead], status_code=status.HTTP_201_CREATED)
async def bulk_mark_attendance(payload: BulkAttendanceCreate, request: Request, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALLOWED_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await writable_selected_academic_session(db, school_id, request, current_user, payload.session_id)
    await _validate_session(db, session.id if session else payload.session_id, school_id)
    await _validate_class(db, payload.class_id, school_id)
    await _assert_teacher_can_access_class(db, school_id, current_user, payload.class_id, session.id if session else payload.session_id)
    resolved_section_name = await validate_class_section_name(db, school_id, payload.class_id, section_name=payload.section_name, section_id=payload.section_id, session_id=session.id if session else payload.session_id)
    student_ids = [e.student_id for e in payload.entries]
    students = await async_query(db, Student).filter(Student.id.in_(student_ids), Student.school_id == school_id, Student.academic_session_id == payload.session_id).all()
    found_ids = {s.id for s in students}
    missing = set(student_ids) - found_ids
    if missing:
        raise HTTPException(status_code=400, detail=f'Students not found: {sorted(missing)}')
    results = []
    students_by_id = {student.id: student for student in students}
    attendance_notifications: list[tuple[Student, str]] = []
    for entry in payload.entries:
        existing = await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.student_id == entry.student_id, StudentAttendance.date == payload.date, StudentAttendance.session_id == payload.session_id).first()
        if existing:
            previous_status = existing.status
            existing.status = entry.status
            existing.note = entry.note
            existing.marked_by = current_user.id
            results.append(existing)
            if entry.status != AttendanceStatus.PRESENT.value and previous_status != entry.status and entry.student_id in students_by_id:
                attendance_notifications.append((students_by_id[entry.student_id], entry.status))
        else:
            record = StudentAttendance(school_id=school_id, session_id=payload.session_id, student_id=entry.student_id, class_id=payload.class_id, section_id=None, section_name=resolved_section_name, date=payload.date, status=entry.status, note=entry.note, marked_by=current_user.id)
            db.add(record)
            results.append(record)
            if entry.status != AttendanceStatus.PRESENT.value and entry.student_id in students_by_id:
                attendance_notifications.append((students_by_id[entry.student_id], entry.status))
    for student, status_value in attendance_notifications:
        await notify_student_record(
            db,
            school_id=school_id,
            student=student,
            title='Attendance update',
            message=f"Attendance marked {status_value.replace('_', ' ').title()} for {format_date(payload.date)}.",
            category='ATTENDANCE',
            priority='HIGH' if status_value == AttendanceStatus.ABSENT.value else 'NORMAL',
            created_by=current_user.id,
            student_link='/attendance/my',
            parent_link='/attendance/my',
        )
    await db.commit()
    for r in results:
        await db.refresh(r)
    return results

@router.get('/sheet', response_model=list[DayAttendanceRecord])
async def get_attendance_sheet(request: Request, session_id: int=Query(...), class_id: int=Query(...), date: date=Query(...), section_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALLOWED_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user, session_id)
    await _validate_session(db, session.id if session else session_id, school_id)
    await _validate_class(db, class_id, school_id)
    await _assert_teacher_can_access_class(db, school_id, current_user, class_id, session.id if session else session_id)
    q = async_query(db, Student).filter(Student.school_id == school_id, Student.class_id == class_id, Student.is_active.is_(True), Student.academic_session_id == session_id)
    if section_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session.id if session else session_id)
        q = q.filter(Student.section_name == section_name)
    students = await q.order_by(Student.roll_number, Student.first_name).all()
    existing = {a.student_id: a for a in await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.class_id == class_id, StudentAttendance.date == date, StudentAttendance.session_id == session_id).all()}
    return [DayAttendanceRecord(student_id=s.id, student_name=_student_full_name(s), admission_no=s.admission_no, roll_number=s.roll_number, status=existing[s.id].status if s.id in existing else None, note=existing[s.id].note if s.id in existing else None, attendance_id=existing[s.id].id if s.id in existing else None) for s in students]

@router.patch('/{attendance_id}', response_model=AttendanceRead)
async def update_attendance(attendance_id: int, payload: AttendanceUpdate, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALLOWED_ROLES)), db: AsyncSession=Depends(get_async_db)):
    record = await async_query(db, StudentAttendance).filter(StudentAttendance.id == attendance_id, StudentAttendance.school_id == school_id).first()
    if not record:
        raise HTTPException(status_code=404, detail='Attendance record not found')
    await assert_item_session_is_writable(db, school_id, record, "session_id")
    await _assert_teacher_can_access_class(db, school_id, current_user, record.class_id, record.session_id)
    previous_status = record.status
    record.status = payload.status
    record.note = payload.note
    record.marked_by = current_user.id
    if payload.status != AttendanceStatus.PRESENT.value and previous_status != payload.status:
        student = await async_query(db, Student).filter(
            Student.school_id == school_id,
            Student.id == record.student_id,
        ).first()
        if student:
            await notify_student_record(
                db,
                school_id=school_id,
                student=student,
                title='Attendance update',
                message=f"Attendance marked {payload.status.replace('_', ' ').title()} for {format_date(record.date)}.",
                category='ATTENDANCE',
                priority='HIGH' if payload.status == AttendanceStatus.ABSENT.value else 'NORMAL',
                created_by=current_user.id,
                student_link='/attendance/my',
                parent_link='/attendance/my',
            )
    await db.commit()
    await db.refresh(record)
    return record

@router.get('/summary', response_model=list[StudentAttendanceSummary])
async def attendance_summary(request: Request, session_id: int=Query(...), class_id: int=Query(...), section_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALLOWED_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user, session_id)
    await _validate_session(db, session.id if session else session_id, school_id)
    await _validate_class(db, class_id, school_id)
    await _assert_teacher_can_access_class(db, school_id, current_user, class_id, session.id if session else session_id)
    q = async_query(db, Student).filter(Student.school_id == school_id, Student.class_id == class_id, Student.is_active.is_(True), Student.academic_session_id == session_id)
    if section_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session.id if session else session_id)
        q = q.filter(Student.section_name == section_name)
    students = await q.order_by(Student.first_name).all()
    student_ids = [s.id for s in students]
    if not student_ids:
        return []
    from sqlalchemy import case as _case, func as _func
    agg_rows = await async_query(db, StudentAttendance.student_id, _func.count(StudentAttendance.id).label('total'), _func.sum(_case((StudentAttendance.status == AttendanceStatus.PRESENT.value, 1), else_=0)).label('present'), _func.sum(_case((StudentAttendance.status == AttendanceStatus.ABSENT.value, 1), else_=0)).label('absent'), _func.sum(_case((StudentAttendance.status == AttendanceStatus.LEAVE.value, 1), else_=0)).label('leave'), _func.sum(_case((StudentAttendance.status == AttendanceStatus.HALF_DAY.value, 1), else_=0)).label('half_day')).filter(StudentAttendance.school_id == school_id, StudentAttendance.student_id.in_(student_ids), StudentAttendance.session_id == session_id).group_by(StudentAttendance.student_id).all()
    agg_map = {row.student_id: row for row in agg_rows}
    summaries = []
    for s in students:
        row = agg_map.get(s.id)
        total = int(row.total or 0) if row else 0
        present = int(row.present or 0) if row else 0
        absent = int(row.absent or 0) if row else 0
        leave = int(row.leave or 0) if row else 0
        half_day = int(row.half_day or 0) if row else 0
        effective = present + half_day * 0.5
        percentage = round(effective / total * 100, 1) if total > 0 else 0.0
        summaries.append(StudentAttendanceSummary(student_id=s.id, student_name=_student_full_name(s), admission_no=s.admission_no, total_days=total, present=present, absent=absent, leave=leave, half_day=half_day, percentage=percentage, low_attendance=percentage < 75 and total > 0))
    return summaries

@router.get('/by-date', response_model=list[AttendanceRead])
async def attendance_by_date(request: Request, session_id: int=Query(...), class_id: int=Query(...), date: date=Query(...), section_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ALLOWED_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user, session_id)
    await _assert_teacher_can_access_class(db, school_id, current_user, class_id, session.id if session else session_id)
    q = async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.class_id == class_id, StudentAttendance.date == date, StudentAttendance.session_id == session_id)
    if section_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session.id if session else session_id)
        q = q.filter(StudentAttendance.section_name == section_name)
    return await q.all()

@router.get('/my', response_model=list[AttendanceRead])
async def my_attendance(request: Request, session_id: int=Query(...), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user, session_id)
    student = await async_query(db, Student).filter(Student.user_id == current_user.id, Student.school_id == school_id, Student.academic_session_id == (session.id if session else session_id)).first()
    if student:
        return await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.student_id == student.id, StudentAttendance.session_id == session_id).order_by(StudentAttendance.date.desc()).all()
    if current_user.role == UserRole.PARENT.value:
        parent_guardians = await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == school_id, ParentGuardian.user_id == current_user.id, ParentGuardian.is_active.is_(True)).all()
        if not parent_guardians:
            return []
        guardian_ids = [pg.id for pg in parent_guardians]
        children = await async_query(db, Student).filter(Student.school_id == school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True), Student.academic_session_id == (session.id if session else session_id)).all()
        if not children:
            return []
        child_ids = [child.id for child in children]
        records = await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.student_id.in_(child_ids), StudentAttendance.session_id == session_id).order_by(StudentAttendance.date.desc()).all()
        for record in records:
            if record.student:
                record.student_name = f"{record.student.first_name} {record.student.last_name or ''}".strip()
        return records
    raise HTTPException(status_code=403, detail="You don't have permission to access this resource")
