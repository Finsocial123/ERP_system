from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, get_current_user, require_school_admin
from app.models.academic import AcademicSession, SchoolClass, Section, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.timetable import TimetableDay, TimetableEntry, TimetablePeriod
from app.models.user import User, UserRole
from app.utils.parent_scope import children_for_parent
from app.schemas.common import MessageResponse
from app.schemas.timetable import TimetableDayCreate, TimetableDayRead, TimetableDayUpdate, TimetableEntryCreate, TimetableEntryRead, TimetableEntryUpdate, TimetableGridResponse, TimetableMetaItem, TimetableMetaResponse, TimetablePeriodCreate, TimetablePeriodRead, TimetablePeriodUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
router = APIRouter(prefix='/timetable', tags=['Phase 7 - Timetable Management'])
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

async def _teacher_for_user(db: AsyncSession, school_id: int, user: User) -> Teacher | None:
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

async def _student_for_user(db: AsyncSession, school_id: int, user: User) -> Student | None:
    student = await async_query(db, Student).filter(Student.school_id == school_id, Student.user_id == user.id).first()
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
    return await async_query(db, Student).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(*conditions)).first()

async def _children_for_parent(db: AsyncSession, school_id: int, user: User) -> list[Student]:
    return await children_for_parent(db, school_id, user)

async def _validate_entry_scope(db: AsyncSession, school_id: int, class_id: int, section_id: int | None, day_id: int, period_id: int, subject_id: int | None, teacher_id: int | None, academic_session_id: int | None) -> None:
    school_class = await _get_or_404(db, SchoolClass, class_id, school_id, 'Class')
    section = await _get_or_404(db, Section, section_id, school_id, 'Section')
    day = await _get_or_404(db, TimetableDay, day_id, school_id, 'Day')
    period = await _get_or_404(db, TimetablePeriod, period_id, school_id, 'Period')
    subject = await _get_or_404(db, Subject, subject_id, school_id, 'Subject')
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id, 'Teacher')
    session = await _get_or_404(db, AcademicSession, academic_session_id, school_id, 'Academic session')
    if not school_class.is_active:
        raise HTTPException(status_code=400, detail='Selected class is inactive')
    if section and section.class_id != class_id:
        raise HTTPException(status_code=400, detail='Selected section does not belong to selected class')
    if day and (not day.is_active):
        raise HTTPException(status_code=400, detail='Selected day is inactive')
    if period and (not period.is_active):
        raise HTTPException(status_code=400, detail='Selected period is inactive')
    if subject and subject.class_id is not None and (subject.class_id != class_id):
        raise HTTPException(status_code=400, detail='Selected subject is linked to another class')
    if teacher and (not teacher.is_active):
        raise HTTPException(status_code=400, detail='Selected teacher is inactive')
    if session and (not session.is_active):
        pass

async def _check_conflicts(db: AsyncSession, school_id: int, payload: dict[str, Any], entry_id: int | None=None) -> None:
    academic_session_id = payload.get('academic_session_id')
    class_id = payload['class_id']
    section_id = payload.get('section_id')
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
    if section_id is not None:
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
    return TimetableEntryRead(id=entry.id, class_id=entry.class_id, section_id=entry.section_id, day_id=entry.day_id, period_id=entry.period_id, subject_id=entry.subject_id, teacher_id=entry.teacher_id, room=entry.room, note=entry.note, academic_session_id=entry.academic_session_id, is_active=entry.is_active, class_name=entry.school_class.name if entry.school_class else None, section_name=entry.section.name if entry.section else None, day_name=entry.day.display_name if entry.day else None, day_of_week=entry.day.day_of_week if entry.day else None, day_sort_order=entry.day.sort_order if entry.day else None, period_name=entry.period.name if entry.period else None, period_number=entry.period.period_number if entry.period else None, start_time=entry.period.start_time if entry.period else None, end_time=entry.period.end_time if entry.period else None, subject_name=entry.subject.name if entry.subject else None, teacher_name=entry.teacher.full_name if entry.teacher else None, academic_session_name=entry.academic_session.name if entry.academic_session else None, created_at=entry.created_at, updated_at=entry.updated_at)

def _entry_query(db: AsyncSession, school_id: int):
    return async_query(db, TimetableEntry).filter(TimetableEntry.school_id == school_id)

def _ordered_entries(query):
    return query.join(TimetableDay, TimetableEntry.day_id == TimetableDay.id).join(TimetablePeriod, TimetableEntry.period_id == TimetablePeriod.id).order_by(TimetableDay.sort_order.asc(), TimetablePeriod.period_number.asc(), TimetableEntry.id.asc())

@router.get('/meta', response_model=TimetableMetaResponse)
async def timetable_meta(school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    current_session = await _current_session(db, school_id)
    classes = await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True)).order_by(SchoolClass.name.asc()).all()
    sections = await async_query(db, Section).filter(Section.school_id == school_id, Section.is_active.is_(True)).order_by(Section.name.asc()).all()
    subjects = await async_query(db, Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True)).order_by(Subject.name.asc()).all()
    teachers = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True)).order_by(Teacher.full_name.asc()).all()
    periods = await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id).order_by(TimetablePeriod.period_number.asc()).all()
    days = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id).order_by(TimetableDay.sort_order.asc()).all()
    sessions = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).all()
    return TimetableMetaResponse(classes=[TimetableMetaItem(id=item.id, name=item.name, extra=item.code) for item in classes], sections=[TimetableMetaItem(id=item.id, name=item.name, extra=str(item.class_id)) for item in sections], subjects=[TimetableMetaItem(id=item.id, name=item.name, extra=str(item.class_id) if item.class_id else None) for item in subjects], teachers=[TimetableMetaItem(id=item.id, name=item.full_name, extra=item.employee_id) for item in teachers], periods=periods, days=days, academic_sessions=[TimetableMetaItem(id=item.id, name=item.name, extra='active' if item.is_active else None) for item in sessions], current_academic_session_id=current_session.id if current_session else None)

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
async def list_entries(class_id: int | None=Query(default=None), section_id: int | None=Query(default=None), teacher_id: int | None=Query(default=None), academic_session_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    query = _entry_query(db, school_id)
    if class_id is not None:
        query = query.filter(TimetableEntry.class_id == class_id)
    if section_id is not None:
        query = query.filter(TimetableEntry.section_id == section_id)
    if teacher_id is not None:
        query = query.filter(TimetableEntry.teacher_id == teacher_id)
    if academic_session_id is not None:
        query = query.filter(TimetableEntry.academic_session_id == academic_session_id)
    entries = _ordered_entries(query).options(joinedload(TimetableEntry.school_class), joinedload(TimetableEntry.section), joinedload(TimetableEntry.day), joinedload(TimetableEntry.period), joinedload(TimetableEntry.subject), joinedload(TimetableEntry.teacher), joinedload(TimetableEntry.academic_session)).all()
    return [_entry_payload(entry) for entry in entries]

@router.post('/entries', response_model=TimetableEntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(payload: TimetableEntryCreate, current_user: User=Depends(require_school_admin), db: AsyncSession=Depends(get_async_db)):
    data = payload.model_dump()
    if data.get('academic_session_id') is None:
        session = await _current_session(db, current_user.school_id)
        if session:
            data['academic_session_id'] = session.id
    data['room'] = data.get('room') or None
    await _validate_entry_scope(db, current_user.school_id, **{k: data.get(k) for k in ['class_id', 'section_id', 'day_id', 'period_id', 'subject_id', 'teacher_id', 'academic_session_id']})
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
    existing = {'class_id': item.class_id, 'section_id': item.section_id, 'day_id': item.day_id, 'period_id': item.period_id, 'subject_id': item.subject_id, 'teacher_id': item.teacher_id, 'room': item.room, 'note': item.note, 'academic_session_id': item.academic_session_id, 'is_active': item.is_active}
    existing.update(payload.model_dump(exclude_unset=True))
    existing['room'] = existing.get('room') or None
    await _validate_entry_scope(db, current_user.school_id, **{k: existing.get(k) for k in ['class_id', 'section_id', 'day_id', 'period_id', 'subject_id', 'teacher_id', 'academic_session_id']})
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
    await db.delete(item)
    await db.commit()
    return {'message': 'Timetable entry deleted'}

@router.get('/view/class', response_model=TimetableGridResponse)
async def view_by_class(class_id: int=Query(...), section_id: int | None=Query(default=None), academic_session_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    school_class = await _get_or_404(db, SchoolClass, class_id, school_id, 'Class')
    section = await _get_or_404(db, Section, section_id, school_id, 'Section')
    query = _entry_query(db, school_id).filter(TimetableEntry.class_id == class_id, TimetableEntry.is_active.is_(True))
    if section_id is not None:
        query = query.filter(TimetableEntry.section_id == section_id)
    if academic_session_id is not None:
        query = query.filter(TimetableEntry.academic_session_id == academic_session_id)
    title = f"{school_class.name}{(' - ' + section.name if section else '')} Timetable"
    periods = await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id, TimetablePeriod.is_active.is_(True)).order_by(TimetablePeriod.period_number.asc()).all()
    days = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id, TimetableDay.is_active.is_(True)).order_by(TimetableDay.sort_order.asc()).all()
    entries = _ordered_entries(query).options(joinedload(TimetableEntry.school_class), joinedload(TimetableEntry.section), joinedload(TimetableEntry.day), joinedload(TimetableEntry.period), joinedload(TimetableEntry.subject), joinedload(TimetableEntry.teacher), joinedload(TimetableEntry.academic_session)).all()
    return TimetableGridResponse(mode='class', title=title, entries=[_entry_payload(e) for e in entries], periods=periods, days=days)

@router.get('/view/teacher', response_model=TimetableGridResponse)
async def view_by_teacher(teacher_id: int=Query(...), academic_session_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), db: AsyncSession=Depends(get_async_db)):
    await _ensure_default_days(db, school_id)
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id, 'Teacher')
    query = _entry_query(db, school_id).filter(TimetableEntry.teacher_id == teacher_id, TimetableEntry.is_active.is_(True))
    if academic_session_id is not None:
        query = query.filter(TimetableEntry.academic_session_id == academic_session_id)
    periods = await async_query(db, TimetablePeriod).filter(TimetablePeriod.school_id == school_id, TimetablePeriod.is_active.is_(True)).order_by(TimetablePeriod.period_number.asc()).all()
    days = await async_query(db, TimetableDay).filter(TimetableDay.school_id == school_id, TimetableDay.is_active.is_(True)).order_by(TimetableDay.sort_order.asc()).all()
    entries = _ordered_entries(query).options(joinedload(TimetableEntry.school_class), joinedload(TimetableEntry.section), joinedload(TimetableEntry.day), joinedload(TimetableEntry.period), joinedload(TimetableEntry.subject), joinedload(TimetableEntry.teacher), joinedload(TimetableEntry.academic_session)).all()
    return TimetableGridResponse(mode='teacher', title=f'{teacher.full_name} Timetable', entries=[_entry_payload(e) for e in entries], periods=periods, days=days)

@router.get('/my-teacher', response_model=TimetableGridResponse)
async def my_teacher_timetable(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.TEACHER.value:
        raise HTTPException(status_code=403, detail='Teacher access required')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    teacher = await _teacher_for_user(db, current_user.school_id, current_user)
    if not teacher:
        return TimetableGridResponse(mode='teacher', title='My Timetable', entries=[], periods=[], days=[])
    return await view_by_teacher(teacher_id=teacher.id, academic_session_id=None, school_id=current_user.school_id, db=db)

@router.get('/my-student', response_model=TimetableGridResponse)
async def my_student_timetable(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.STUDENT.value:
        raise HTTPException(status_code=403, detail='Student access required')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    student = await _student_for_user(db, current_user.school_id, current_user)
    if not student or not student.class_id:
        return TimetableGridResponse(mode='student', title='My Class Timetable', entries=[], periods=[], days=[])
    return await view_by_class(class_id=student.class_id, section_id=student.section_id, academic_session_id=None, school_id=current_user.school_id, db=db)

@router.get('/my-children', response_model=list[TimetableGridResponse])
async def my_children_timetable(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if current_user.role != UserRole.PARENT.value:
        raise HTTPException(status_code=403, detail='Parent access required')
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    children = await _children_for_parent(db, current_user.school_id, current_user)
    result: list[TimetableGridResponse] = []
    for child in children:
        if not child.class_id:
            continue
        grid = await view_by_class(class_id=child.class_id, section_id=child.section_id, academic_session_id=None, school_id=current_user.school_id, db=db)
        grid.title = f"{child.first_name} {child.last_name or ''}".strip() + ' - ' + grid.title
        result.append(grid)
    return result
