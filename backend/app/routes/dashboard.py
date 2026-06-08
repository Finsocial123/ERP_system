from datetime import date, datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, inspect, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.async_query import async_query
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, get_current_user
from app.models.academic import AcademicSession, Department, SchoolClass, Section, Subject
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.exam import Exam, ExamMark, ExamSubject
from app.models.fee import FeeExpense, FeePayment, StudentFeeRecord
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.school import School
from app.models.timetable import TimetableEntry
from app.models.user import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
router = APIRouter(prefix='/dashboard', tags=['Phase 3 - Dashboard and Quick Analytics'])
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}

def _iso(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()

async def _count(db: AsyncSession, query) -> int:
    return int(await query.count() or 0)

async def _current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    today = date.today()
    active = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True)).order_by(AcademicSession.id.desc()).first()
    if active:
        return active
    by_date = await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id, AcademicSession.start_date <= today, AcademicSession.end_date >= today).order_by(AcademicSession.id.desc()).first()
    if by_date:
        return by_date
    return await async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()

def _session_payload(session: AcademicSession | None) -> dict[str, Any] | None:
    if not session:
        return None
    return {'id': session.id, 'name': session.name, 'start_date': _iso(session.start_date), 'end_date': _iso(session.end_date), 'is_active': session.is_active}

def _full_student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name or ''}".strip()

async def _admin_counts(db: AsyncSession, school_id: int) -> dict[str, int]:
    return {'academic_sessions': await _count(db, async_query(db, AcademicSession).filter(AcademicSession.school_id == school_id)), 'departments': await _count(db, async_query(db, Department).filter(Department.school_id == school_id)), 'classes': await _count(db, async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True))), 'sections': await _count(db, async_query(db, Section).filter(Section.school_id == school_id, Section.is_active.is_(True))), 'subjects': await _count(db, async_query(db, Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True))), 'students': await _count(db, async_query(db, Student).filter(Student.school_id == school_id, Student.is_active.is_(True))), 'teachers': await _count(db, async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True))), 'homework': await _count(db, async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.is_active.is_(True))), 'timetable_slots': await _count(db, async_query(db, TimetableEntry).filter(TimetableEntry.school_id == school_id, TimetableEntry.is_active.is_(True))), 'exams': await _count(db, async_query(db, Exam).filter(Exam.school_id == school_id, Exam.is_active.is_(True))), 'published_results': await _count(db, async_query(db, Exam).filter(Exam.school_id == school_id, Exam.is_active.is_(True), Exam.result_status == 'PUBLISHED')), 'fee_records': await _count(db, async_query(db, StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id)), 'pending_fee_records': await _count(db, async_query(db, StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id, StudentFeeRecord.status.in_(['PENDING', 'PARTIAL', 'OVERDUE'])))}

async def _new_admissions_count(db: AsyncSession, school_id: int, days: int=30) -> int:
    since_date = date.today() - timedelta(days=days)
    since_datetime = datetime.combine(since_date, datetime.min.time())
    return await _count(db, async_query(db, Student).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(Student.admission_date >= since_date, Student.created_at >= since_datetime)))

async def _optional_table_count(db: AsyncSession, table_names: list[str], school_id: int, date_columns: list[str] | None=None, date_value: date | None=None, status_columns: list[str] | None=None, status_values: list[str] | None=None) -> int:
    """Safely count optional/future tables using AsyncSession-compatible inspection.

    SQLAlchemy cannot inspect an AsyncEngine directly, so table/column inspection
    must run through an AsyncConnection.run_sync callback.
    """

    def _inspect_existing_tables(sync_conn):
        inspector = inspect(sync_conn)
        existing_tables = set(inspector.get_table_names())
        return {
            table_name: {column['name'] for column in inspector.get_columns(table_name)}
            for table_name in table_names
            if table_name in existing_tables
        }

    try:
        connection = await db.connection()
        table_columns = await connection.run_sync(_inspect_existing_tables)
    except Exception:
        return 0

    for table_name, columns in table_columns.items():
        where = []
        params: dict[str, Any] = {}
        if 'school_id' in columns:
            where.append('school_id = :school_id')
            params['school_id'] = school_id
        if date_columns and date_value:
            date_column = next((column for column in date_columns if column in columns), None)
            if date_column:
                where.append(f'{date_column} = :date_value')
                params['date_value'] = date_value
        if status_columns and status_values:
            status_column = next((column for column in status_columns if column in columns), None)
            if status_column:
                placeholders = []
                for index, value in enumerate(status_values):
                    key = f'status_{index}'
                    placeholders.append(f':{key}')
                    params[key] = value.upper()
                where.append(f"UPPER({status_column}) IN ({', '.join(placeholders)})")
        sql = f'SELECT COUNT(*) FROM {table_name}'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        try:
            return int((await db.execute(text(sql), params)).scalar() or 0)
        except Exception:
            return 0
    return 0

async def _today_attendance_count(db: AsyncSession, school_id: int) -> int:
    return await _optional_table_count(db, table_names=['student_attendance'], school_id=school_id, date_columns=['attendance_date', 'date', 'marked_date'], date_value=date.today())

async def _teacher_today_attendance_count(db: AsyncSession, school_id: int, teacher: Teacher | None) -> int:
    """
    Count today's attendance records only for the classes where the teacher
    is assigned as class teacher (ClassTeacherAssignment).
    Returns 0 if teacher has no class assignments.
    """
    if not teacher:
        return 0
    assigned_class_ids = [row.class_id for row in await async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.teacher_id == teacher.id, ClassTeacherAssignment.school_id == school_id).all()]
    if not assigned_class_ids:
        return 0
    return await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.class_id.in_(assigned_class_ids), StudentAttendance.date == date.today()).count()

async def _pending_fees_count(db: AsyncSession, school_id: int) -> int:
    return await _count(db, async_query(db, StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id, StudentFeeRecord.status.in_(['PENDING', 'PARTIAL', 'OVERDUE'])))

async def _pending_fee_amount_for_school(db: AsyncSession, school_id: int) -> float:
    return round(float(await async_query(db, StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id, StudentFeeRecord.status.in_(['PENDING', 'PARTIAL', 'OVERDUE'])).with_entities(func.coalesce(func.sum(StudentFeeRecord.balance_amount), 0)).scalar() or 0), 2)

async def _today_fee_collection(db: AsyncSession, school_id: int) -> float:
    return round(float(await async_query(db, FeePayment).filter(FeePayment.school_id == school_id, FeePayment.payment_date == date.today()).with_entities(func.coalesce(func.sum(FeePayment.amount), 0)).scalar() or 0), 2)

async def _pending_fee_amount_for_students(db: AsyncSession, school_id: int, student_ids: list[int]) -> float:
    if not student_ids:
        return 0.0
    return round(float(await async_query(db, StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id, StudentFeeRecord.student_id.in_(student_ids), StudentFeeRecord.status.in_(['PENDING', 'PARTIAL', 'OVERDUE'])).with_entities(func.coalesce(func.sum(StudentFeeRecord.balance_amount), 0)).scalar() or 0), 2)

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
    student = await async_query(db, Student).options(
        selectinload(Student.school_class),
        selectinload(Student.section),
        selectinload(Student.guardian),
    ).filter(Student.school_id == school_id, Student.user_id == user.id).first()
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
    return await async_query(db, Student).options(
        selectinload(Student.school_class),
        selectinload(Student.section),
        selectinload(Student.guardian),
    ).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(*conditions)).first()

def _parent_identifiers(user: User) -> set[str]:
    return {str(item).strip().lower() for item in (user.email, user.login_id) if item and str(item).strip()}

async def _guardians_for_parent_user(db: AsyncSession, school_id: int, user: User) -> list[ParentGuardian]:
    """Safely resolve guardian records for a parent dashboard.

    Never match by phone number. Shared/demo phone numbers caused each parent to
    see the total school student count. If old data linked multiple guardians to
    one parent user, keep only records whose guardian email matches this login.
    """
    identifiers = _parent_identifiers(user)
    linked = await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == school_id, ParentGuardian.user_id == user.id, ParentGuardian.is_active.is_(True)).order_by(ParentGuardian.id.asc()).all()
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
    return await async_query(db, ParentGuardian).filter(ParentGuardian.school_id == school_id, ParentGuardian.is_active.is_(True), func.lower(ParentGuardian.email).in_(identifiers)).order_by(ParentGuardian.id.asc()).all()

async def _children_for_parent(db: AsyncSession, school_id: int, user: User) -> list[Student]:
    guardians = await _guardians_for_parent_user(db, school_id, user)
    guardian_ids = [guardian.id for guardian in guardians]
    if not guardian_ids:
        return []
    return await async_query(db, Student).options(
        selectinload(Student.school_class),
        selectinload(Student.section),
        selectinload(Student.guardian),
    ).filter(Student.school_id == school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True)).order_by(Student.id.desc()).all()

async def _teacher_student_count(db: AsyncSession, school_id: int, teacher: Teacher | None) -> int:
    if not teacher:
        return 0
    scopes: set[tuple[int | None, int | None]] = set()
    subject_assignments = await async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id).all()
    class_assignments = await async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id).all()
    for assignment in subject_assignments:
        if assignment.class_id:
            scopes.add((assignment.class_id, assignment.section_id))
    for assignment in class_assignments:
        scopes.add((assignment.class_id, assignment.section_id))
    student_ids: set[int] = set()
    for class_id, section_id in scopes:
        query = async_query(db, Student.id).filter(Student.school_id == school_id, Student.is_active.is_(True))
        if class_id:
            query = query.filter(Student.class_id == class_id)
        if section_id:
            query = query.filter(Student.section_id == section_id)
        student_ids.update((row[0] for row in await query.all()))
    return len(student_ids)

def _homework_assignments_for_student_query(db: AsyncSession, school_id: int, student: Student):
    return async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.class_id == student.class_id, HomeworkAssignment.is_active.is_(True), or_(HomeworkAssignment.section_id.is_(None), HomeworkAssignment.section_id == student.section_id))

async def _pending_homework_for_student(db: AsyncSession, school_id: int, student: Student | None) -> int:
    if not student or not student.class_id:
        return 0
    assignments = await _homework_assignments_for_student_query(db, school_id, student).all()
    if not assignments:
        return 0
    assignment_ids = [item.id for item in assignments]
    submitted_ids = {row[0] for row in await async_query(db, HomeworkSubmission.homework_id).filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.student_id == student.id, HomeworkSubmission.homework_id.in_(assignment_ids)).all()}
    return len([item for item in assignments if item.id not in submitted_ids])

async def _teacher_homework_counts(db: AsyncSession, school_id: int, user: User) -> dict[str, int]:
    teacher = await _teacher_for_user(db, school_id, user)
    if not teacher:
        return {'homework_created': 0, 'submissions_to_check': 0}
    homework_created = await _count(db, async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.teacher_id == teacher.id, HomeworkAssignment.is_active.is_(True)))
    submissions_to_check = await async_query(db, HomeworkSubmission).join(HomeworkAssignment, HomeworkSubmission.homework_id == HomeworkAssignment.id).filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.status == 'SUBMITTED', HomeworkAssignment.teacher_id == teacher.id, HomeworkAssignment.is_active.is_(True)).count()
    return {'homework_created': homework_created, 'submissions_to_check': submissions_to_check}

async def _teacher_timetable_slots(db: AsyncSession, school_id: int, user: User) -> int:
    teacher = await _teacher_for_user(db, school_id, user)
    if not teacher:
        return 0
    return await _count(db, async_query(db, TimetableEntry).filter(TimetableEntry.school_id == school_id, TimetableEntry.teacher_id == teacher.id, TimetableEntry.is_active.is_(True)))

async def _student_timetable_slots(db: AsyncSession, school_id: int, student: Student | None) -> int:
    if not student or not student.class_id:
        return 0
    query = async_query(db, TimetableEntry).filter(TimetableEntry.school_id == school_id, TimetableEntry.class_id == student.class_id, TimetableEntry.is_active.is_(True))
    if student.section_id is not None:
        query = query.filter(or_(TimetableEntry.section_id.is_(None), TimetableEntry.section_id == student.section_id))
    return await _count(db, query)

async def _pending_homework_for_children(db: AsyncSession, school_id: int, children: list[Student]) -> int:
    total = 0
    for child in children:
        total += await _pending_homework_for_student(db, school_id, child)
    return total

async def _teacher_exam_counts(db: AsyncSession, school_id: int, user: User) -> dict[str, int]:
    teacher = await _teacher_for_user(db, school_id, user)
    if not teacher:
        return {'exam_subjects': 0, 'marks_entered': 0, 'published_exams': 0}
    exam_subject_ids = [row.id for row in await async_query(db, ExamSubject.id).join(Exam, ExamSubject.exam_id == Exam.id).filter(ExamSubject.school_id == school_id, ExamSubject.teacher_id == teacher.id, ExamSubject.is_active.is_(True), Exam.is_active.is_(True)).all()]
    marks_entered = 0
    if exam_subject_ids:
        marks_entered = await _count(db, async_query(db, ExamMark).filter(ExamMark.school_id == school_id, ExamMark.exam_subject_id.in_(exam_subject_ids)))
    published_exams = await _count(db, async_query(db, Exam).join(ExamSubject, ExamSubject.exam_id == Exam.id).filter(Exam.school_id == school_id, Exam.is_active.is_(True), Exam.result_status == 'PUBLISHED', ExamSubject.teacher_id == teacher.id, ExamSubject.is_active.is_(True)).distinct())
    return {'exam_subjects': len(exam_subject_ids), 'marks_entered': marks_entered, 'published_exams': published_exams}

async def _published_exams_for_student(db: AsyncSession, school_id: int, student: Student | None) -> int:
    if not student or not student.class_id:
        return 0
    query = async_query(db, Exam).filter(Exam.school_id == school_id, Exam.class_id == student.class_id, Exam.is_active.is_(True), Exam.result_status == 'PUBLISHED')
    if student.section_id is not None:
        query = query.filter(or_(Exam.section_id.is_(None), Exam.section_id == student.section_id))
    return await _count(db, query)

async def _published_exams_for_children(db: AsyncSession, school_id: int, children: list[Student]) -> int:
    total = 0
    for child in children:
        total += await _published_exams_for_student(db, school_id, child)
    return total

async def _recent_activities(db: AsyncSession, school_id: int, role: str, limit: int=8) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []

    def add(kind: str, title: str, description: str | None, created_at: datetime | date | None):
        activities.append({'kind': kind, 'title': title, 'description': description, 'created_at': _iso(created_at)})
    session = await _current_session(db, school_id)
    if session:
        add('academic_session', 'Current academic session', session.name, session.created_at)
    if role in ADMIN_ROLES or role == UserRole.TEACHER.value:
        for student in await async_query(db, Student).filter(Student.school_id == school_id).order_by(Student.created_at.desc()).limit(4).all():
            add('student', 'Student added', f'{_full_student_name(student)} · Admission No: {student.admission_no}', student.created_at)
    if role in ADMIN_ROLES:
        for teacher in await async_query(db, Teacher).filter(Teacher.school_id == school_id).order_by(Teacher.created_at.desc()).limit(3).all():
            add('teacher', 'Teacher added', f'{teacher.full_name} · Employee ID: {teacher.employee_id}', teacher.created_at)
    for homework in await async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.is_active.is_(True)).order_by(HomeworkAssignment.created_at.desc()).limit(4).all():
        add('homework', 'Homework assigned', homework.title, homework.created_at)
    for exam in await async_query(db, Exam).filter(Exam.school_id == school_id, Exam.is_active.is_(True)).order_by(Exam.created_at.desc()).limit(4).all():
        status_label = 'Result published' if exam.result_status == 'PUBLISHED' else 'Exam created'
        add('exam', status_label, exam.name, exam.published_at or exam.created_at)
    for subject in await async_query(db, Subject).filter(Subject.school_id == school_id).order_by(Subject.created_at.desc()).limit(3).all():
        add('subject', 'Subject configured', subject.name, subject.created_at)
    for school_class in await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id).order_by(SchoolClass.created_at.desc()).limit(3).all():
        add('class', 'Class configured', school_class.name, school_class.created_at)
    activities.sort(key=lambda item: item.get('created_at') or '', reverse=True)
    return activities[:limit]

async def _admin_charts(db: AsyncSession, school_id: int, counts: dict[str, int]) -> list[dict[str, Any]]:
    class_rows = await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True)).order_by(SchoolClass.name.asc()).all()
    students_by_class = []
    for school_class in class_rows:
        students_by_class.append({'label': school_class.name, 'value': await _count(db, async_query(db, Student).filter(Student.school_id == school_id, Student.class_id == school_class.id, Student.is_active.is_(True)))})
    setup_summary = [{'label': 'Classes', 'value': counts['classes']}, {'label': 'Sections', 'value': counts['sections']}, {'label': 'Subjects', 'value': counts['subjects']}, {'label': 'Departments', 'value': counts['departments']}, {'label': 'Exams', 'value': counts.get('exams', 0)}, {'label': 'Fee Records', 'value': counts.get('fee_records', 0)}]
    people_summary = [{'label': 'Students', 'value': counts['students']}, {'label': 'Teachers', 'value': counts['teachers']}]
    return [{'title': 'People overview', 'type': 'bar', 'items': people_summary}, {'title': 'Academic setup', 'type': 'bar', 'items': setup_summary}, {'title': 'Students by class', 'type': 'bar', 'items': students_by_class or [{'label': 'No classes', 'value': 0}]}]

async def _student_attendance_percentage(db: AsyncSession, school_id: int, student: Student | None, session: AcademicSession | None) -> str:
    """Return attendance % string for the student card. Returns '—' if no data yet."""
    if not student or not session:
        return '—'
    records = await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.student_id == student.id, StudentAttendance.session_id == session.id).all()
    total = len(records)
    if total == 0:
        return '—'
    present = sum((1 for r in records if r.status == AttendanceStatus.PRESENT.value))
    half_day = sum((1 for r in records if r.status == AttendanceStatus.HALF_DAY.value))
    effective = present + half_day * 0.5
    pct = round(effective / total * 100, 1)
    return f'{pct}%'

def _card(key: str, label: str, value: int | str, helper: str='', tone: str='default') -> dict[str, Any]:
    return {'key': key, 'label': label, 'value': value, 'helper': helper, 'tone': tone}

async def _admin_dashboard(db: AsyncSession, school_id: int) -> dict[str, Any]:
    counts = await _admin_counts(db, school_id)
    session = await _current_session(db, school_id)
    new_admissions = await _new_admissions_count(db, school_id)
    today_attendance = await _today_attendance_count(db, school_id)
    pending_fees = await _pending_fees_count(db, school_id)
    pending_fee_amount = await _pending_fee_amount_for_school(db, school_id)
    today_fee_collection = await _today_fee_collection(db, school_id)
    cards = [_card('teachers', 'Total Teachers', counts['teachers'], 'Active teaching staff'), _card('students', 'Total Students', counts['students'], 'Active student records'), _card('today_attendance', 'Today Attendance', today_attendance, 'Marked records for today', 'info'), _card('pending_fees', 'Pending Fees', pending_fees, 'Pending/partial/overdue student fee records', 'warning'), _card('pending_fee_amount', 'Pending Fee Amount', f'₹{pending_fee_amount:,.2f}', 'Total unpaid balance', 'warning'), _card('today_fee_collection', 'Today Collection', f'₹{today_fee_collection:,.2f}', 'Fee payments collected today', 'success'), _card('new_admissions', 'New Admissions', new_admissions, 'Admissions in the last 30 days', 'success'), _card('current_session', 'Current Academic Session', session.name if session else 'Not set', 'Active/latest session'), _card('homework', 'Homework Assigned', counts['homework'], 'Total active homework assignments', 'success'), _card('timetable_slots', 'Timetable Slots', counts['timetable_slots'], 'Active class timetable entries', 'info'), _card('exams', 'Exams', counts['exams'], 'Active exams created', 'info'), _card('published_results', 'Published Results', counts['published_results'], 'Exams visible to students and parents', 'success')]
    counts.update({'today_attendance': today_attendance, 'pending_fees': pending_fees, 'pending_fee_amount': pending_fee_amount, 'today_fee_collection': today_fee_collection, 'new_admissions': new_admissions})
    return {'role_dashboard': 'admin', 'title': 'Admin Dashboard', 'description': 'Quick analytics for students, staff, attendance, fees and academic setup.', 'cards': cards, 'counts': counts, 'current_academic_session': _session_payload(session), 'recent_activities': await _recent_activities(db, school_id, UserRole.SCHOOL_ADMIN.value), 'charts': await _admin_charts(db, school_id, counts), 'next_steps': ['Attendance Management', 'Fees', 'Exams', 'Communication', 'Reports']}

async def _teacher_dashboard(db: AsyncSession, school_id: int, user: User) -> dict[str, Any]:
    teacher = await _teacher_for_user(db, school_id, user)
    my_subjects = 0
    my_classes = 0
    total_students = 0
    if teacher:
        my_subjects = await _count(db, async_query(db, TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id))
        my_classes = await _count(db, async_query(db, ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id))
        total_students = await _teacher_student_count(db, school_id, teacher)
    homework_counts = await _teacher_homework_counts(db, school_id, user)
    timetable_slots = await _teacher_timetable_slots(db, school_id, user)
    exam_counts = await _teacher_exam_counts(db, school_id, user)
    cards = [_card('my_subjects', 'My Subjects', my_subjects, 'Assigned subject scopes'), _card('my_classes', 'My Classes', my_classes, 'Class teacher assignments'), _card('total_students', 'My Students', total_students, 'Students in assigned classes'), _card('today_attendance', 'Today Attendance', await _teacher_today_attendance_count(db, school_id, teacher), 'Students marked present/absent today in your classes', 'info'), _card('homework_created', 'Homework Created', homework_counts['homework_created'], 'Active homework assignments', 'success'), _card('submissions_to_check', 'Submissions To Check', homework_counts['submissions_to_check'], 'Submitted homework waiting for checking', 'warning'), _card('timetable_slots', 'Timetable Slots', timetable_slots, 'Assigned weekly teaching slots', 'info'), _card('exam_subjects', 'Exam Subjects', exam_counts['exam_subjects'], 'Subjects assigned for marks entry', 'info'), _card('marks_entered', 'Marks Entered', exam_counts['marks_entered'], 'Student marks saved by exam subject', 'success')]
    return {'role_dashboard': 'teacher', 'title': 'Teacher Dashboard', 'description': 'Assigned classes, students, attendance and upcoming homework tools.', 'cards': cards, 'counts': {card['key']: card['value'] for card in cards if isinstance(card['value'], int)}, 'current_academic_session': _session_payload(await _current_session(db, school_id)), 'recent_activities': await _recent_activities(db, school_id, UserRole.TEACHER.value), 'charts': [{'title': 'Teacher workload', 'type': 'bar', 'items': [{'label': 'Subjects', 'value': my_subjects}, {'label': 'Classes', 'value': my_classes}, {'label': 'Students', 'value': total_students}, {'label': 'Homework', 'value': homework_counts['homework_created']}, {'label': 'To Check', 'value': homework_counts['submissions_to_check']}, {'label': 'Timetable', 'value': timetable_slots}, {'label': 'Exam Subjects', 'value': exam_counts['exam_subjects']}, {'label': 'Marks', 'value': exam_counts['marks_entered']}]}], 'next_steps': ['Create homework', 'Check submissions', 'View timetable', 'Enter marks']}

async def _student_dashboard(db: AsyncSession, school_id: int, user: User) -> dict[str, Any]:
    student = await _student_for_user(db, school_id, user)
    session = await _current_session(db, school_id)
    class_label = 'Not assigned'
    if student and student.school_class:
        class_label = student.school_class.name
        if student.section:
            class_label += f' - {student.section.name}'
    pending_homework = await _pending_homework_for_student(db, school_id, student)
    timetable_slots = await _student_timetable_slots(db, school_id, student)
    published_results = await _published_exams_for_student(db, school_id, student)
    student_fee_ids = [student.id] if student else []
    student_pending_fee_amount = await _pending_fee_amount_for_students(db, school_id, student_fee_ids)
    att_pct = await _student_attendance_percentage(db, school_id, student, session)
    att_tone = 'info'
    if att_pct != '—':
        raw = float(att_pct.replace('%', ''))
        att_tone = 'warning' if raw < 75 else 'success' if raw >= 90 else 'info'
    attendance_chart_value = 0
    if att_pct != '—':
        attendance_chart_value = round(float(att_pct.replace('%', '')), 1)
    cards = [_card('homework', 'Pending Homework', pending_homework, 'Assignments waiting for your submission', 'warning'), _card('attendance_percent', 'Attendance %', att_pct, f"Current session attendance ({(session.name if session else 'N/A')})", att_tone), _card('pending_fees', 'Pending Fees', f'₹{student_pending_fee_amount:,.2f}', 'Your unpaid fee balance', 'warning'), _card('notices', 'Notices', 0, 'Communication module comes in Phase 9'), _card('timetable_slots', 'Timetable Slots', timetable_slots, 'Weekly class timetable slots', 'info'), _card('published_results', 'Published Results', published_results, 'Report cards available to view', 'success'), _card('current_class', 'Current Class', class_label, 'Student class and section')]
    return {'role_dashboard': 'student', 'title': 'Student Dashboard', 'description': 'Student quick view for homework, attendance, fees and notices.', 'cards': cards, 'counts': {card['key']: card['value'] for card in cards if isinstance(card['value'], int)}, 'current_academic_session': _session_payload(await _current_session(db, school_id)), 'recent_activities': await _recent_activities(db, school_id, UserRole.STUDENT.value), 'charts': [{'title': 'Student summary', 'type': 'bar', 'items': [{'label': 'Homework', 'value': pending_homework}, {'label': 'Notices', 'value': 0}, {'label': 'Timetable', 'value': timetable_slots}, {'label': 'Results', 'value': published_results}]}], 'next_steps': ['View homework', 'View report cards', 'View fees', 'Check notices']}

async def _parent_dashboard(db: AsyncSession, school_id: int, user: User) -> dict[str, Any]:
    children = await _children_for_parent(db, school_id, user)
    pending_homework = await _pending_homework_for_children(db, school_id, children)
    timetable_slots = 0
    for child in children:
        timetable_slots += await _student_timetable_slots(db, school_id, child)
    published_results = await _published_exams_for_children(db, school_id, children)
    child_pending_fee_amount = await _pending_fee_amount_for_students(db, school_id, [child.id for child in children])
    session = await _current_session(db, school_id)
    low_att_count = 0
    for child in children:
        pct_str = await _student_attendance_percentage(db, school_id, child, session)
        if pct_str != '—' and float(pct_str.replace('%', '')) < 75:
            low_att_count += 1
    att_alert_helper = f"{low_att_count} child{('ren' if low_att_count != 1 else '')} below 75%" if low_att_count > 0 else 'All children above 75% attendance'
    cards = [_card('children', 'Children', len(children), 'Linked active student profiles'), _card('pending_homework', 'Pending Homework', pending_homework, 'Homework pending for linked children', 'warning'), _card('pending_fees', 'Pending Fees', f'₹{child_pending_fee_amount:,.2f}', 'Unpaid fee balance for linked children', 'warning'), _card('notices', 'Notices', 0, 'Communication module comes in Phase 9'), _card('timetable_slots', 'Timetable Slots', timetable_slots, 'Weekly slots for linked children', 'info'), _card('attendance_alerts', 'Attendance Alerts', low_att_count, att_alert_helper, 'warning' if low_att_count > 0 else 'success'), _card('published_results', 'Published Results', published_results, 'Child report cards available', 'success')]
    return {'role_dashboard': 'parent', 'title': 'Parent Dashboard', 'description': 'Parent quick view for child attendance, fees, notices and alerts.', 'cards': cards, 'counts': {card['key']: card['value'] for card in cards if isinstance(card['value'], int)}, 'current_academic_session': _session_payload(await _current_session(db, school_id)), 'recent_activities': await _recent_activities(db, school_id, UserRole.PARENT.value), 'charts': [{'title': 'Parent summary', 'type': 'bar', 'items': [{'label': 'Children', 'value': len(children)}, {'label': 'Homework', 'value': pending_homework}, {'label': 'Fees', 'value': 0}, {'label': 'Alerts', 'value': 0}, {'label': 'Timetable', 'value': timetable_slots}, {'label': 'Results', 'value': published_results}]}], 'next_steps': ['Child attendance', 'Child results', 'Fee status', 'Homework', 'Notices']}

@router.get('/overview')
async def overview(school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    school = await db.get(School, school_id)
    role = current_user.role
    if role == UserRole.TEACHER.value:
        dashboard = await _teacher_dashboard(db, school_id, current_user)
    elif role == UserRole.STUDENT.value:
        dashboard = await _student_dashboard(db, school_id, current_user)
    elif role == UserRole.PARENT.value:
        dashboard = await _parent_dashboard(db, school_id, current_user)
    else:
        dashboard = await _admin_dashboard(db, school_id)
    return {'school': {'id': school.id, 'name': school.name, 'type': school.institution_type, 'school_code': school.school_code} if school else None, 'user': {'id': current_user.id, 'full_name': current_user.full_name, 'role': current_user.role, 'login_id': current_user.login_id, 'must_change_password': current_user.must_change_password}, 'phase': 'Phase 8 - Exam and Result Management', 'quick_search_enabled': True, **dashboard}

@router.get('/quick-search')
async def quick_search(q: str=Query(default='', min_length=0), limit: int=Query(default=8, ge=1, le=20), school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    query_text = q.strip()
    if not query_text:
        return {'query': query_text, 'results': []}
    like = f'%{query_text}%'
    results: list[dict[str, Any]] = []

    def add(kind: str, title: str, subtitle: str, href: str | None=None):
        if len(results) < limit:
            results.append({'kind': kind, 'title': title, 'subtitle': subtitle, 'href': href})
    if current_user.role in ADMIN_ROLES or current_user.role == UserRole.TEACHER.value:
        students = await async_query(db, Student).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(Student.first_name.ilike(like), Student.last_name.ilike(like), Student.admission_no.ilike(like), Student.roll_number.ilike(like), Student.email.ilike(like))).order_by(Student.id.desc()).limit(limit).all()
        for student in students:
            add('student', _full_student_name(student), f'Admission No: {student.admission_no}', '/students')
    if current_user.role in ADMIN_ROLES:
        teachers = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True), or_(Teacher.full_name.ilike(like), Teacher.employee_id.ilike(like), Teacher.email.ilike(like))).order_by(Teacher.id.desc()).limit(limit).all()
        for teacher in teachers:
            add('teacher', teacher.full_name, f'Employee ID: {teacher.employee_id}', '/teachers')
    classes = await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True), SchoolClass.name.ilike(like)).order_by(SchoolClass.id.desc()).limit(limit).all()
    for school_class in classes:
        add('class', school_class.name, 'Class setup', '/setup/classes' if current_user.role in ADMIN_ROLES else None)
    subjects = await async_query(db, Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True), Subject.name.ilike(like)).order_by(Subject.id.desc()).limit(limit).all()
    for subject in subjects:
        add('subject', subject.name, 'Subject setup', '/setup/subjects' if current_user.role in ADMIN_ROLES else None)
    homework_query = async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.is_active.is_(True), or_(HomeworkAssignment.title.ilike(like), HomeworkAssignment.description.ilike(like)))
    if current_user.role == UserRole.TEACHER.value:
        teacher = await _teacher_for_user(db, school_id, current_user)
        homework_query = homework_query.filter(HomeworkAssignment.teacher_id == teacher.id) if teacher else homework_query.filter(HomeworkAssignment.id == -1)
    for homework in await homework_query.order_by(HomeworkAssignment.created_at.desc()).limit(limit).all():
        href = '/teacher-homework' if current_user.role == UserRole.TEACHER.value else '/homework' if current_user.role in ADMIN_ROLES else None
        add('homework', homework.title, f'Due: {homework.due_date.isoformat()}', href)
    exam_query = async_query(db, Exam).filter(Exam.school_id == school_id, Exam.is_active.is_(True), or_(Exam.name.ilike(like), Exam.exam_type.ilike(like), Exam.description.ilike(like)))
    if current_user.role == UserRole.TEACHER.value:
        teacher = await _teacher_for_user(db, school_id, current_user)
        if teacher:
            exam_query = exam_query.join(ExamSubject, ExamSubject.exam_id == Exam.id).filter(ExamSubject.teacher_id == teacher.id)
        else:
            exam_query = exam_query.filter(Exam.id == -1)
    elif current_user.role == UserRole.STUDENT.value:
        student = await _student_for_user(db, school_id, current_user)
        if student and student.class_id:
            exam_query = exam_query.filter(Exam.class_id == student.class_id, Exam.result_status == 'PUBLISHED')
            if student.section_id is not None:
                exam_query = exam_query.filter(or_(Exam.section_id.is_(None), Exam.section_id == student.section_id))
        else:
            exam_query = exam_query.filter(Exam.id == -1)
    elif current_user.role == UserRole.PARENT.value:
        children = await _children_for_parent(db, school_id, current_user)
        class_ids = [child.class_id for child in children if child.class_id]
        if class_ids:
            exam_query = exam_query.filter(Exam.result_status == 'PUBLISHED', Exam.class_id.in_(class_ids))
        else:
            exam_query = exam_query.filter(Exam.id == -1)
    for exam in await exam_query.order_by(Exam.created_at.desc()).limit(limit).all():
        if current_user.role == UserRole.TEACHER.value:
            href = '/teacher-exams'
        elif current_user.role == UserRole.STUDENT.value:
            href = '/student-exams'
        elif current_user.role == UserRole.PARENT.value:
            href = '/parent-exams'
        else:
            href = '/exams'
        add('exam', exam.name, f"{exam.exam_type or 'Exam'} · {exam.result_status}", href)
    return {'query': query_text, 'results': results[:limit]}
