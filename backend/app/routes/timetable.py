from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.core.database import get_async_db
from app.core.sections import class_section_options, validate_class_section_name
from app.dependencies.auth import current_school_id, get_current_user, require_school_admin
from app.dependencies.academic_session import selected_academic_session, require_writable_academic_session, writable_selected_academic_session, assert_item_session_is_writable
from app.models.academic import AcademicSession, SchoolClass, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.timetable import TimetableDay, TimetableEntry, TimetablePeriod
from app.models.user import User, UserRole
from app.utils.parent_scope import children_for_parent
from app.schemas.common import MessageResponse
from app.schemas.timetable import TimetableDayCreate, TimetableDayRead, TimetableDayUpdate, TimetableEntryCreate, TimetableEntryRead, TimetableEntryUpdate, TimetableGridResponse, TimetableMetaItem, TimetableMetaResponse, TimetablePeriodCreate, TimetablePeriodRead, TimetablePeriodUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
router = APIRouter(prefix='/timetable', tags=['Phase 7 - Timetable Management'], dependencies=[Depends(require_writable_academic_session)])
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
DEFAULT_DAYS = [('MONDAY', 'Monday', 1), ('TUESDAY', 'Tuesday', 2), ('WEDNESDAY', 'Wednesday', 3), ('THURSDAY', 'Thursday', 4), ('FRIDAY', 'Friday', 5), ('SATURDAY', 'Saturday', 6)]

async def _get_or_404(db: AsyncSession, model, item_id: int | None, school_id: int, name: str):
    if item_id is None:
        return None
    item = await async_query(db, model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f'{name} not found for this school')
    return item

async def _current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    today = date.today()
    active = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True)).order_by(AcademicSession.id.desc()).first()
    if active:
        return active
    by_date = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id, AcademicSession.start_date <= today, AcademicSession.end_date >= today).order_by(AcademicSession.id.desc()).first()
    if by_date:
        return by_date
    return await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()

async def _ensure_default_days(db: AsyncSession, school_id: int) -> None:
    existing_count = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id).count()
    if existing_count:
        return
    for day_of_week, display_name, sort_order in DEFAULT_DAYS:
        db.add(TimetableDay(school_id=school_id, day_of_week=day_of_week, display_name=display_name, sort_order=sort_order))
    await db.commit()

async def _teacher_for_user(db: AsyncSession, school_id: int, user: User, academic_session_id: int | None=None) -> Teacher | None:
    query = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.user_id == user.id)
    if academic_session_id is not None:
        query = query.filter(Teacher.academic_session_id == academic_session_id)
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
    if academic_session_id is not None:
        query = query.filter(Teacher.academic_session_id == academic_session_id)
    return await query.first()

async def _student_for_user(db: AsyncSession, school_id: int, user: User, academic_session_id: int | None=None) -> Student | None:
    query = async_query(db, Student).filter(Student.school_id == school_id, Student.user_id == user.id)
    if academic_session_id is not None:
        query = query.filter(Student.academic_session_id == academic_session_id)
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
    if academic_session_id is not None:
        query = query.filter(Student.academic_session_id == academic_session_id)
    return await query.first()

async def _children_for_parent(db: AsyncSession, school_id: int, user: User, academic_session_id: int | None=None) -> list[Student]:
    children = await children_for_parent(db, school_id, user)
    if academic_session_id is None:
        return children
    return [child for child in children if child.academic_session_id == academic_session_id]

async def _validate_entry_scope(
    db: AsyncSession,
    school_id: int,
    class_id: int,
    section_id: int | None,
    day_id: int,
    period_id: int,
    subject_id: int | None,
    teacher_id: int | None,
    academic_session_id: int | None,
    section_name: str | None = None,
) -> str | None:
    school_class = await _get_or_404(db, SchoolClass, class_id, school_id, 'Class')
    resolved_section_name = await validate_class_section_name(
        db,
        school_id,
        class_id,
        section_name=section_name,
        section_id=section_id,
        session_id=academic_session_id,
    )
    day = await _get_or_404(db, TimetableDay, day_id, school_id, 'Day')
    period = await _get_or_404(db, TimetablePeriod, period_id, school_id, 'Period')
    subject = await _get_or_404(db, Subject, subject_id, school_id, 'Subject')
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id, 'Teacher')
    session = await _get_or_404(db, AcademicSession, academic_session_id, school_id, 'Academic session')
    if not school_class.is_active:
        raise HTTPException(status_code=400, detail='Selected class is inactive')
    if day and (not day.is_active):
        raise HTTPException(status_code=400, detail='Selected day is inactive')
    if period and (not period.is_active):
        raise HTTPException(status_code=400, detail='Selected period is inactive')
    if subject and subject.class_id != class_id:
        raise HTTPException(status_code=400, detail='Selected subject does not belong to selected class')
    if teacher and (not teacher.is_active):
        raise HTTPException(status_code=400, detail='Selected teacher is inactive')
    if session and (not session.is_active):
        pass
    return resolved_section_name

async def _check_conflicts(db: AsyncSession, school_id: int, payload: dict[str, Any], entry_id: int | None=None) -> None:
    academic_session_id = payload.get('academic_session_id')
    class_id = payload['class_id']
    section_id = payload.get('section_id')
    section_name = payload.get('section_name')
    day_id = payload['day_id']
    period_id = payload['period_id']
    teacher_id = payload.get('teacher_id')
    room = (payload.get('room') or '').strip()
    base_filters = [TimetableEntry.school_id == school_id, TimetableEntry.day_id == day_id, TimetableEntry.period_id == period_id, TimetableEntry.is_active.is_(True)]
    if academic_session_id is None:
        base_filters.append(TimetableEntry.academic_session_id.is_(None))
    else:
        base_filters.append(TimetableEntry.academic_session_id == academic_session_id)
    class_filters = list(base_filters) + [TimetableEntry.class_id == class_id]
    if section_name:
        class_filters.append(or_(TimetableEntry.section_name.is_(None), TimetableEntry.section_name == section_name))
    elif section_id is not None:
        class_filters.append(or_(TimetableEntry.section_id.is_(None), TimetableEntry.section_id == section_id))
    class_query = async_query(db, TimetableEntry).filter(*class_filters)
    if entry_id:
        class_query = class_query.filter(TimetableEntry.id != entry_id)
    if await class_query.first():
        raise HTTPException(status_code=400, detail='This class/section already has a timetable entry in the selected day and period')
    if teacher_id is not None:
        teacher_query = async_query(db, TimetableEntry).filter(*base_filters, TimetableEntry.teacher_id == teacher_id)
        if entry_id:
            teacher_query = teacher_query.filter(TimetableEntry.id != entry_id)
        if await teacher_query.first():
            raise HTTPException(status_code=400, detail='Selected teacher is already assigned in this day and period')
    if room:
        room_query = async_query(db, TimetableEntry).filter(*base_filters, func.lower(TimetableEntry.room) == room.lower())
        if entry_id:
            room_query = room_query.filter(TimetableEntry.id != entry_id)
        if await room_query.first():
            raise HTTPException(status_code=400, detail='Selected room is already assigned in this day and period')

def _entry_payload(entry: TimetableEntry) -> TimetableEntryRead:
    school_class = entry.__dict__.get("school_class")
    day = entry.__dict__.get("day")
    period = entry.__dict__.get("period")
    subject = entry.__dict__.get("subject")
    teacher = entry.__dict__.get("teacher")
    academic_session = entry.__dict__.get("academic_session")

    return TimetableEntryRead(
        id=entry.id,
        class_id=entry.class_id,
        section_id=entry.section_id,
        day_id=entry.day_id,
        period_id=entry.period_id,
        subject_id=entry.subject_id,
        teacher_id=entry.teacher_id,
        room=entry.room,
        note=entry.note,
        academic_session_id=entry.academic_session_id,
        is_active=entry.is_active,

        class_name=school_class.name if school_class else None,
        section_name=entry.section_name,
        day_name=day.display_name if day else None,
        day_of_week=day.day_of_week if day else None,
        day_sort_order=day.sort_order if day else None,
        period_name=period.name if period else None,
        period_number=period.period_number if period else None,
        start_time=period.start_time if period else None,
        end_time=period.end_time if period else None,
        subject_name=subject.name if subject else None,
        teacher_name=teacher.full_name if teacher else None,
        academic_session_name=academic_session.name if academic_session else None,

        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )

def _entry_query(db: AsyncSession, school_id: int):
    return async_query(db, TimetableEntry).filter(TimetableEntry.school_id == school_id)

def _ordered_entries(query):
    return query.join(TimetableDay, TimetableEntry.day_id == TimetableDay.id).join(TimetablePeriod, TimetableEntry.period_id == TimetablePeriod.id).order_by(TimetableDay.sort_order.asc(), TimetablePeriod.period_number.asc(), TimetableEntry.id.asc())

@router.get('/meta', response_model=TimetableMetaResponse)
async def timetable_meta(request: Request, school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    current_session = await selected_academic_session(db, school_id, request, current_user)
    session_id = current_session.id if current_session else None
    classes_q = async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True))
    subjects_q = async_query(db, Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True))
    teachers_q = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True))
    if session_id is not None:
        classes_q = classes_q.filter(SchoolClass.academic_session_id == session_id)
        subjects_q = subjects_q.filter(Subject.academic_session_id == session_id)
        teachers_q = teachers_q.filter(Teacher.academic_session_id == session_id)
    classes = await classes_q.order_by(SchoolClass.name.asc()).all()
    subjects = await subjects_q.order_by(Subject.name.asc()).all()
    teachers = await teachers_q.order_by(Teacher.full_name.asc()).all()
    periods = await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id).order_by(TimetablePeriod.period_number.asc()).all()
    days = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id).order_by(TimetableDay.sort_order.asc()).all()
    sessions = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).all()
    return TimetableMetaResponse(classes=[TimetableMetaItem(id=item.id, name=item.name, extra=item.code) for item in classes], sections=[TimetableMetaItem(id=item.id, name=item.name, extra=str(item.extra)) for item in await class_section_options(db, school_id, session_id=session_id)], subjects=[TimetableMetaItem(id=item.id, name=item.name, extra=str(item.class_id) if item.class_id else None) for item in subjects], teachers=[TimetableMetaItem(id=item.id, name=item.full_name, extra=item.employee_id) for item in teachers], periods=periods, days=days, academic_sessions=[TimetableMetaItem(id=item.id, name=item.name, extra='active' if item.is_active else None) for item in sessions], current_academic_session_id=session_id)

@router.get('/periods', response_model=list[TimetablePeriodRead])
async def list_periods(school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    return await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id).order_by(TimetablePeriod.period_number.asc()).all()

@router.post('/periods', response_model=TimetablePeriodRead, status_code=status.HTTP_201_CREATED)
async def create_period(payload: TimetablePeriodCreate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = TimetablePeriod(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail='Period number already exists for this school')
    await db.refresh(item)
    return item

@router.put('/periods/{period_id}', response_model=TimetablePeriodRead)
async def update_period(period_id: int, payload: TimetablePeriodUpdate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = await _get_or_404(db, TimetablePeriod, period_id, current_user.school_id, 'Period')
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail='Period number already exists for this school')
    await db.refresh(item)
    return item

@router.delete('/periods/{period_id}', response_model=MessageResponse)
async def delete_period(period_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = await _get_or_404(db, TimetablePeriod, period_id, current_user.school_id, 'Period')
    in_use = await async_query(db, TimetableEntry).filter(TimetableEntry.school_id == current_user.school_id, TimetableEntry.period_id == period_id).first()
    if in_use:
        raise HTTPException(status_code=400, detail='This period is used in timetable entries. Disable it or delete entries first')
    await db.delete(item)
    await db.commit()
    return {'message': 'Period deleted'}

@router.get('/days', response_model=list[TimetableDayRead])
async def list_days(school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    return await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id).order_by(TimetableDay.sort_order.asc()).all()

@router.post('/days', response_model=TimetableDayRead, status_code=status.HTTP_201_CREATED)
async def create_day(payload: TimetableDayCreate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = TimetableDay(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail='Day already exists for this school')
    await db.refresh(item)
    return item

@router.put('/days/{day_id}', response_model=TimetableDayRead)
async def update_day(day_id: int, payload: TimetableDayUpdate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = await _get_or_404(db, TimetableDay, day_id, current_user.school_id, 'Day')
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail='Day already exists for this school')
    await db.refresh(item)
    return item

@router.delete('/days/{day_id}', response_model=MessageResponse)
async def delete_day(day_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = await _get_or_404(db, TimetableDay, day_id, current_user.school_id, 'Day')
    in_use = await async_query(db, TimetableEntry).filter(TimetableEntry.school_id == current_user.school_id, TimetableEntry.day_id == day_id).first()
    if in_use:
        raise HTTPException(status_code=400, detail='This day is used in timetable entries. Disable it or delete entries first')
    await db.delete(item)
    await db.commit()
    return {'message': 'Day deleted'}

@router.get('/entries', response_model=list[TimetableEntryRead])
async def list_entries(request: Request, class_id: int | None=Query(default=None), section_id: int | None=Query(default=None), teacher_id: int | None=Query(default=None), academic_session_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user, academic_session_id)
    query = _entry_query(db, school_id)
    if class_id is not None:
        query = query.filter(TimetableEntry.class_id == class_id)
    if section_id is not None and class_id is not None:
        resolved_section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session.id if session else None)
        query = query.filter(TimetableEntry.section_name == resolved_section_name)
    elif section_id is not None:
        query = query.filter(TimetableEntry.section_id == section_id)
    if teacher_id is not None:
        query = query.filter(TimetableEntry.teacher_id == teacher_id)
    if session is not None:
        query = query.filter(TimetableEntry.academic_session_id == session.id)
    entries = await _ordered_entries(query).options(
    joinedload(TimetableEntry.school_class),
        joinedload(TimetableEntry.day),
    joinedload(TimetableEntry.period),
    joinedload(TimetableEntry.subject),
    joinedload(TimetableEntry.teacher),
    joinedload(TimetableEntry.academic_session),
).all()
    return [_entry_payload(entry) for entry in entries]

@router.post('/entries', response_model=TimetableEntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(payload: TimetableEntryCreate, request: Request, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    data = payload.model_dump()
    session = await writable_selected_academic_session(db, current_user.school_id, request, current_user, data.get('academic_session_id'))
    if session:
        data['academic_session_id'] = session.id
    data['room'] = data.get('room') or None
    resolved_section_name = await _validate_entry_scope(db, current_user.school_id, **{k: data.get(k) for k in ['class_id', 'section_id', 'day_id', 'period_id', 'subject_id', 'teacher_id', 'academic_session_id']}, section_name=data.get('section_name'))
    data['section_id'] = None
    data['section_name'] = resolved_section_name
    await _check_conflicts(db, current_user.school_id, data)
    item = TimetableEntry(school_id=current_user.school_id, **data)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail='Timetable slot already exists for this class/section')
    await db.refresh(item)
    return _entry_payload(item)

@router.put('/entries/{entry_id}', response_model=TimetableEntryRead)
async def update_entry(entry_id: int, payload: TimetableEntryUpdate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = await _get_or_404(db, TimetableEntry, entry_id, current_user.school_id, 'Timetable entry')
    await assert_item_session_is_writable(db, current_user.school_id, item)
    existing = {'class_id': item.class_id, 'section_id': item.section_id, 'section_name': item.section_name, 'day_id': item.day_id, 'period_id': item.period_id, 'subject_id': item.subject_id, 'teacher_id': item.teacher_id, 'room': item.room, 'note': item.note, 'academic_session_id': item.academic_session_id, 'is_active': item.is_active}
    existing.update(payload.model_dump(exclude_unset=True))
    existing['room'] = existing.get('room') or None
    resolved_section_name = await _validate_entry_scope(db, current_user.school_id, **{k: existing.get(k) for k in ['class_id', 'section_id', 'day_id', 'period_id', 'subject_id', 'teacher_id', 'academic_session_id']}, section_name=existing.get('section_name'))
    existing['section_id'] = None
    existing['section_name'] = resolved_section_name
    if existing.get('is_active'):
        await _check_conflicts(db, current_user.school_id, existing, entry_id=item.id)
    for key, value in existing.items():
        setattr(item, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail='Timetable slot already exists for this class/section')
    await db.refresh(item)
    return _entry_payload(item)

@router.delete('/entries/{entry_id}', response_model=MessageResponse)
async def delete_entry(entry_id: int, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    item = await _get_or_404(db, TimetableEntry, entry_id, current_user.school_id, 'Timetable entry')
    await assert_item_session_is_writable(db, current_user.school_id, item)
    await db.delete(item)
    await db.commit()
    return {'message': 'Timetable entry deleted'}

@router.get('/view/class', response_model=TimetableGridResponse)
async def view_by_class(request: Request, class_id: int=Query(...), section_id: int | None=Query(default=None), section_name: str | None=Query(default=None), academic_session_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    session = await selected_academic_session(db, school_id, request, current_user, academic_session_id)
    school_class = await _get_or_404(db, SchoolClass, class_id, school_id, 'Class')
    section_name = await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id, session_id=session.id if session else None)
    query = _entry_query(db, school_id).filter(TimetableEntry.class_id == class_id, TimetableEntry.is_active.is_(True))
    if section_name:
        query = query.filter(TimetableEntry.section_name == section_name)
    elif section_id is not None:
        query = query.filter(TimetableEntry.section_id == section_id)
    if session is not None:
        query = query.filter(TimetableEntry.academic_session_id == session.id)
    title = f"{school_class.name}{(' - ' + section_name if section_name else '')} Timetable"
    periods = await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id, TimetablePeriod.is_active.is_(True)).order_by(TimetablePeriod.period_number.asc()).all()
    days = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id, TimetableDay.is_active.is_(True)).order_by(TimetableDay.sort_order.asc()).all()
    entries = await _ordered_entries(query).options(
    joinedload(TimetableEntry.school_class),
        joinedload(TimetableEntry.day),
    joinedload(TimetableEntry.period),
    joinedload(TimetableEntry.subject),
    joinedload(TimetableEntry.teacher),
    joinedload(TimetableEntry.academic_session),
).all()
    return TimetableGridResponse(mode='class', title=title, entries=[_entry_payload(e) for e in entries], periods=periods, days=days)

@router.get('/view/teacher', response_model=TimetableGridResponse)
async def view_by_teacher(request: Request, teacher_id: int=Query(...), academic_session_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    session = await selected_academic_session(db, school_id, request, current_user, academic_session_id)
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id, 'Teacher')
    query = _entry_query(db, school_id).filter(TimetableEntry.teacher_id == teacher_id, TimetableEntry.is_active.is_(True))
    if session is not None:
        query = query.filter(TimetableEntry.academic_session_id == session.id)
    periods = await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id, TimetablePeriod.is_active.is_(True)).order_by(TimetablePeriod.period_number.asc()).all()
    days = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id, TimetableDay.is_active.is_(True)).order_by(TimetableDay.sort_order.asc()).all()
    entries = await _ordered_entries(query).options(
    joinedload(TimetableEntry.school_class),
        joinedload(TimetableEntry.day),
    joinedload(TimetableEntry.period),
    joinedload(TimetableEntry.subject),
    joinedload(TimetableEntry.teacher),
    joinedload(TimetableEntry.academic_session),
).all()
    return TimetableGridResponse(mode='teacher', title=f'{teacher.full_name} Timetable', entries=[_entry_payload(e) for e in entries], periods=periods, days=days)

@router.get('/my-teacher', response_model=TimetableGridResponse)
async def my_teacher_timetable(request: Request, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.TEACHER.value:
        raise HTTPException(status_code=403, detail='Teacher access required')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    session = await selected_academic_session(db, current_user.school_id, request, current_user)
    teacher = await _teacher_for_user(db, current_user.school_id, current_user, session.id if session else None)
    if not teacher:
        return TimetableGridResponse(mode='teacher', title='My Timetable', entries=[], periods=[], days=[])
    return await view_by_teacher(request=request, teacher_id=teacher.id, academic_session_id=session.id if session else None, school_id=current_user.school_id, current_user=current_user, db=db)

@router.get('/my-student', response_model=TimetableGridResponse)
async def my_student_timetable(request: Request, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.STUDENT.value:
        raise HTTPException(status_code=403, detail='Student access required')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    session = await selected_academic_session(db, current_user.school_id, request, current_user)
    student = await _student_for_user(db, current_user.school_id, current_user, session.id if session else None)
    if not student or not student.class_id:
        return TimetableGridResponse(mode='student', title='My Class Timetable', entries=[], periods=[], days=[])
    return await view_by_class(request=request, class_id=student.class_id, section_id=student.section_id, section_name=student.section_name, academic_session_id=student.academic_session_id, school_id=current_user.school_id, current_user=current_user, db=db)

@router.get('/my-children', response_model=list[TimetableGridResponse])
async def my_children_timetable(request: Request, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.PARENT.value:
        raise HTTPException(status_code=403, detail='Parent access required')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    session = await selected_academic_session(db, current_user.school_id, request, current_user)
    children = await _children_for_parent(db, current_user.school_id, current_user, session.id if session else None)
    result: list[TimetableGridResponse] = []
    for child in children:
        if not child.class_id:
            continue
        grid = await view_by_class(request=request, class_id=child.class_id, section_id=child.section_id, section_name=child.section_name, academic_session_id=child.academic_session_id, school_id=current_user.school_id, current_user=current_user, db=db)
        grid.title = f"{child.first_name} {child.last_name or ''}".strip() + ' - ' + grid.title
        result.append(grid)
    return result
