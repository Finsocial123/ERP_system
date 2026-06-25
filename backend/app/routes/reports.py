from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import joinedload
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, require_roles
from app.dependencies.academic_session import selected_academic_session
from app.models.academic import AcademicSession, Department, SchoolClass
from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.exam import Exam
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.library import Book, BookIssue, IssueStatus
from app.models.people import ParentGuardian, Student, Teacher, TeacherSubject, ClassTeacherAssignment
from app.models.user import User, UserRole
from app.schemas.reports import AttendanceReportResponse, AttendanceReportRow, HomeworkReportResponse, HomeworkReportRow, ReportsOverview, StudentReportResponse, StudentReportRow, TeacherReportResponse, TeacherReportRow
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
from app.core.sections import validate_class_section_name
router = APIRouter(prefix='/reports', tags=['Phase 10 - Reports'])
ADMIN_ROLES = [UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN]

def _student_name(s: Student) -> str:
    return f"{s.first_name} {s.last_name or ''}".strip()

def _att_pct(present: int, half_day: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((present + half_day * 0.5) / total * 100, 1)

@router.get('/overview', response_model=ReportsOverview)
async def reports_overview(request: Request, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    today = date.today()
    session = await selected_academic_session(db, school_id, request, current_user)
    session_id = session.id if session else None
    total_students = await async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id).count()
    active_students = await async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id, Student.is_active.is_(True)).count()
    total_teachers = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.academic_session_id == session_id).count()
    active_teachers = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.academic_session_id == session_id, Teacher.is_active.is_(True)).count()
    total_classes = await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.academic_session_id == session_id, SchoolClass.is_active.is_(True)).count()
    total_exams = await async_query(db, Exam).filter(Exam.school_id == school_id, Exam.academic_session_id == session_id, Exam.is_active.is_(True)).count()
    published_exams = await async_query(db, Exam).filter(Exam.school_id == school_id, Exam.academic_session_id == session_id, Exam.result_status == 'PUBLISHED').count()
    total_homework = await async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.academic_session_id == session_id, HomeworkAssignment.is_active.is_(True)).count()
    avg_att = 0.0
    low_att_count = 0
    if session_id:
        att_records = await async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.session_id == session_id).all()
        student_map: dict[int, dict] = {}
        for r in att_records:
            if r.student_id not in student_map:
                student_map[r.student_id] = {'total': 0, 'present': 0, 'half': 0}
            student_map[r.student_id]['total'] += 1
            if r.status == AttendanceStatus.PRESENT.value:
                student_map[r.student_id]['present'] += 1
            elif r.status == AttendanceStatus.HALF_DAY.value:
                student_map[r.student_id]['half'] += 1
        if student_map:
            pcts = [_att_pct(v['present'], v['half'], v['total']) for v in student_map.values()]
            avg_att = round(sum(pcts) / len(pcts), 1)
            low_att_count = sum((1 for p in pcts if p < 75))
    lib_books = await async_query(db, Book).filter(Book.school_id == school_id, Book.is_active.is_(True)).count()
    lib_issued = await async_query(db, BookIssue).filter(BookIssue.school_id == school_id, BookIssue.status.in_([IssueStatus.ISSUED.value, IssueStatus.OVERDUE.value])).count()
    lib_overdue = await async_query(db, BookIssue).filter(BookIssue.school_id == school_id, BookIssue.status.in_([IssueStatus.ISSUED.value, IssueStatus.OVERDUE.value]), BookIssue.due_date < today).count()
    return ReportsOverview(total_students=total_students, active_students=active_students, total_teachers=total_teachers, active_teachers=active_teachers, total_classes=total_classes, total_exams=total_exams, published_exams=published_exams, total_homework=total_homework, avg_attendance_pct=avg_att, low_attendance_students=low_att_count, library_books=lib_books, library_issued=lib_issued, overdue_books=lib_overdue)

@router.get('/students', response_model=StudentReportResponse)
async def student_report(request: Request, class_id: int | None=Query(default=None), section_id: int | None=Query(default=None), include_inactive: bool=Query(default=False), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user)
    session_id = session.id if session else None
    q = async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id)
    if not include_inactive:
        q = q.filter(Student.is_active.is_(True))
    if class_id:
        q = q.filter(Student.class_id == class_id)
    if section_id and class_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session_id)
        q = q.filter(Student.section_name == section_name)
    elif section_id:
        q = q.filter(Student.section_id == section_id)
    students = await q.order_by(Student.first_name).all()
    class_map = {c.id: c.name for c in await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.academic_session_id == session_id).all()}
    rows = []
    for s in students:
        guardian = await async_query(db, ParentGuardian).filter(ParentGuardian.students.contains(s), ParentGuardian.is_active.is_(True)).first()
        rows.append(StudentReportRow(student_id=s.id, admission_no=s.admission_no, roll_number=s.roll_number, full_name=_student_name(s), gender=s.gender, class_name=class_map.get(s.class_id) if s.class_id else None, section_name=s.section_name, guardian_name=guardian.full_name if guardian else None, guardian_phone=guardian.phone if guardian else None, admission_date=str(s.admission_date) if s.admission_date else None, status=s.status if s.status else 'ACTIVE' if s.is_active else 'INACTIVE'))
    total = await async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id).count()
    active = await async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id, Student.is_active.is_(True)).count()
    class_counts = {}
    for s in await async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id, Student.is_active.is_(True)).all():
        key = class_map.get(s.class_id, 'Unassigned') if s.class_id else 'Unassigned'
        class_counts[key] = class_counts.get(key, 0) + 1
    class_breakdown = [{'class': k, 'count': v} for k, v in sorted(class_counts.items())]
    return StudentReportResponse(total_students=total, active_students=active, class_breakdown=class_breakdown, rows=rows)

@router.get('/attendance', response_model=AttendanceReportResponse)
async def attendance_report(request: Request, session_id: int | None=Query(default=None), class_id: int | None=Query(default=None), section_id: int | None=Query(default=None), date_from: date | None=Query(default=None), date_to: date | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    selected_session = await selected_academic_session(db, school_id, request, current_user)
    session_id = session_id or (selected_session.id if selected_session else None)
    session = await async_query(db, AcademicSession).filter(AcademicSession.id == session_id, AcademicSession.school_id == school_id).first()
    class_map = {c.id: c.name for c in await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.academic_session_id == session_id).all()}
    sq = async_query(db, Student).filter(Student.school_id == school_id, Student.academic_session_id == session_id, Student.is_active.is_(True))
    if class_id:
        sq = sq.filter(Student.class_id == class_id)
    if section_id and class_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session_id)
        sq = sq.filter(Student.section_name == section_name)
    elif section_id:
        sq = sq.filter(Student.section_id == section_id)
    students = await sq.order_by(Student.first_name).all()
    aq = async_query(db, StudentAttendance).filter(StudentAttendance.school_id == school_id, StudentAttendance.session_id == session_id)
    if class_id:
        aq = aq.filter(StudentAttendance.class_id == class_id)
    if section_id and class_id:
        aq = aq.filter(StudentAttendance.section_name == section_name)
    elif section_id:
        aq = aq.filter(StudentAttendance.section_id == section_id)
    if date_from:
        aq = aq.filter(StudentAttendance.date >= date_from)
    if date_to:
        aq = aq.filter(StudentAttendance.date <= date_to)
    records = await aq.all()
    record_map: dict[int, dict] = {}
    for r in records:
        if r.student_id not in record_map:
            record_map[r.student_id] = {'total': 0, 'present': 0, 'absent': 0, 'leave': 0, 'half': 0}
        record_map[r.student_id]['total'] += 1
        if r.status == AttendanceStatus.PRESENT.value:
            record_map[r.student_id]['present'] += 1
        elif r.status == AttendanceStatus.ABSENT.value:
            record_map[r.student_id]['absent'] += 1
        elif r.status == AttendanceStatus.LEAVE.value:
            record_map[r.student_id]['leave'] += 1
        elif r.status == AttendanceStatus.HALF_DAY.value:
            record_map[r.student_id]['half'] += 1
    rows = []
    for s in students:
        d = record_map.get(s.id, {'total': 0, 'present': 0, 'absent': 0, 'leave': 0, 'half': 0})
        pct = _att_pct(d['present'], d['half'], d['total'])
        rows.append(AttendanceReportRow(student_id=s.id, student_name=_student_name(s), admission_no=s.admission_no, roll_number=s.roll_number, class_name=class_map.get(s.class_id) if s.class_id else None, section_name=s.section_name, total_days=d['total'], present=d['present'], absent=d['absent'], leave=d['leave'], half_day=d['half'], percentage=pct, low_attendance=pct < 75 and d['total'] > 0))
    avg_pct = round(sum((r.percentage for r in rows)) / len(rows), 1) if rows else 0.0
    low_count = sum((1 for r in rows if r.low_attendance))
    return AttendanceReportResponse(session_id=session_id, session_name=session.name if session else str(session_id), class_id=class_id, class_name=class_map.get(class_id) if class_id else None, section_id=section_id, date_from=date_from, date_to=date_to, total_students=len(rows), avg_percentage=avg_pct, low_attendance_count=low_count, rows=rows)

@router.get('/teachers', response_model=TeacherReportResponse)
async def teacher_report(request: Request, department_id: int | None=Query(default=None), include_inactive: bool=Query(default=False), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    session = await selected_academic_session(db, school_id, request, current_user)
    session_id = session.id if session else None
    dept_map = {d.id: d.name for d in await async_query(db, Department).filter(Department.school_id == school_id, Department.academic_session_id == session_id).all()}
    q = async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.academic_session_id == session_id)
    if not include_inactive:
        q = q.filter(Teacher.is_active.is_(True))
    if department_id:
        q = q.filter(Teacher.department_id == department_id)
    teachers = await q.order_by(Teacher.full_name).all()
    from sqlalchemy import func as _func
    teacher_ids = [t.id for t in teachers]
    subj_counts = dict(await async_query(db, TeacherSubject.teacher_id, _func.count(TeacherSubject.id)).filter(TeacherSubject.teacher_id.in_(teacher_ids), TeacherSubject.academic_session_id == session_id).group_by(TeacherSubject.teacher_id).all()) if teacher_ids else {}
    class_counts = dict(await async_query(db, ClassTeacherAssignment.teacher_id, _func.count(ClassTeacherAssignment.id)).filter(ClassTeacherAssignment.teacher_id.in_(teacher_ids), ClassTeacherAssignment.academic_session_id == session_id).group_by(ClassTeacherAssignment.teacher_id).all()) if teacher_ids else {}
    rows = []
    for t in teachers:
        subjects_count = subj_counts.get(t.id, 0)
        classes_count = class_counts.get(t.id, 0)
        rows.append(TeacherReportRow(teacher_id=t.id, employee_id=t.employee_id, full_name=t.full_name, photo_url=t.photo_url, department_name=dept_map.get(t.department_id) if t.department_id else None, email=t.email, phone=t.phone, qualification=t.qualification, joining_date=str(t.joining_date) if t.joining_date else None, status=t.status if t.status else 'ACTIVE' if t.is_active else 'INACTIVE', subjects_assigned=subjects_count, classes_assigned=classes_count))
    total = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.academic_session_id == session_id).count()
    active = await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.academic_session_id == session_id, Teacher.is_active.is_(True)).count()
    dept_counts: dict = {}
    for t in await async_query(db, Teacher).filter(Teacher.school_id == school_id, Teacher.academic_session_id == session_id, Teacher.is_active.is_(True)).all():
        key = dept_map.get(t.department_id, 'No Department') if t.department_id else 'No Department'
        dept_counts[key] = dept_counts.get(key, 0) + 1
    dept_breakdown = [{'department': k, 'count': v} for k, v in sorted(dept_counts.items())]
    return TeacherReportResponse(total_teachers=total, active_teachers=active, department_breakdown=dept_breakdown, rows=rows)

@router.get('/homework', response_model=HomeworkReportResponse)
async def homework_report(request: Request, session_id: int | None=Query(default=None), class_id: int | None=Query(default=None), school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    selected_session = await selected_academic_session(db, school_id, request, current_user)
    session_id = session_id or (selected_session.id if selected_session else None)
    class_map = {c.id: c.name for c in await async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.academic_session_id == session_id).all()}
    session_name = None
    if session_id:
        s = await async_query(db, AcademicSession).filter(AcademicSession.id == session_id, AcademicSession.school_id == school_id).first()
        session_name = s.name if s else None
    q = async_query(db, HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.is_active.is_(True))
    if session_id:
        q = q.filter(HomeworkAssignment.academic_session_id == session_id)
    if class_id:
        q = q.filter(HomeworkAssignment.class_id == class_id)
    assignments = await q.order_by(HomeworkAssignment.due_date.desc()).all()
    from sqlalchemy import func as _func2, case as _case2
    from app.models.homework import HomeworkSubmission as _HWSub
    class_section_pairs = list({(hw.class_id, hw.section_name) for hw in assignments})
    student_count_map = {}
    for class_id_k, section_name_k in class_section_pairs:
        q = async_query(db, _func2.count(Student.id)).filter(Student.school_id == school_id, Student.academic_session_id == session_id, Student.is_active.is_(True), Student.class_id == class_id_k)
        if section_name_k:
            q = q.filter(Student.section_name == section_name_k)
        student_count_map[class_id_k, section_name_k] = await q.scalar() or 0
    hw_ids = [hw.id for hw in assignments]
    sub_counts = {}
    if hw_ids:
        for row in await async_query(db, _HWSub.homework_id, _func2.sum(_case2((_HWSub.status.in_(['SUBMITTED', 'CHECKED']), 1), else_=0)).label('submitted'), _func2.sum(_case2((_HWSub.status == 'CHECKED', 1), else_=0)).label('checked')).filter(_HWSub.homework_id.in_(hw_ids)).group_by(_HWSub.homework_id).all():
            sub_counts[row.homework_id] = {'submitted': int(row.submitted or 0), 'checked': int(row.checked or 0)}
    rows = []
    for hw in assignments:
        total_students = student_count_map.get((hw.class_id, hw.section_name), 0)
        sc = sub_counts.get(hw.id, {'submitted': 0, 'checked': 0})
        submitted = sc['submitted']
        checked = sc['checked']
        pending = max(0, total_students - submitted)
        rate = round(submitted / total_students * 100, 1) if total_students > 0 else 0.0
        teacher_name = None
        if hw.teacher_id:
            t = await async_query(db, Teacher).filter(Teacher.id == hw.teacher_id).first()
            teacher_name = t.full_name if t else None
        subject_name = None
        if hw.subject_id:
            from app.models.academic import Subject
            subj = await async_query(db, Subject).filter(Subject.id == hw.subject_id).first()
            subject_name = subj.name if subj else None
        rows.append(HomeworkReportRow(assignment_id=hw.id, title=hw.title, subject_name=subject_name, class_name=class_map.get(hw.class_id), section_name=hw.section_name, due_date=hw.due_date, teacher_name=teacher_name, total_students=total_students, submitted=submitted, checked=checked, pending=pending, submission_rate=rate))
    return HomeworkReportResponse(session_id=session_id, session_name=session_name, class_id=class_id, rows=rows)

@router.get('/fees')
async def fee_report(school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    return {'message': 'Fee management module (Phase 6) not yet implemented.', 'total_collected': 0, 'total_pending': 0, 'rows': []}
