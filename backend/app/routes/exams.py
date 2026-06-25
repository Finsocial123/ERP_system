from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_query import async_query
from app.core.database import get_async_db
from app.core.sections import class_section_options, validate_class_section_name
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.dependencies.academic_session import selected_academic_session, require_writable_academic_session, writable_selected_academic_session, assert_item_session_is_writable, assert_academic_session_is_writable
from app.models.academic import AcademicSession, SchoolClass, Subject
from app.models.exam import Exam, ExamMark, ExamSubject
from app.models.people import Student, Teacher
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.exam import (
    ClassResultResponse,
    ExamBulkMarksPayload,
    ExamCreate,
    ExamMarkRead,
    ExamMetaItem,
    ExamMetaResponse,
    ExamRead,
    ExamStudentRead,
    ExamSubjectCreate,
    ExamSubjectRead,
    ExamSubjectResultRead,
    ExamSubjectUpdate,
    ExamTimetableItem,
    ExamUpdate,
    ParentReportCard,
    ReportCardSubject,
    StudentReportCard,
)
from app.utils.parent_scope import children_for_parent
from app.services.notification_service import format_date, notify_student_scope, notify_teacher_record


router = APIRouter(prefix="/exams", tags=["Phase 8 - Exam and Result Management"], dependencies=[Depends(require_writable_academic_session)])

ADMIN_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
}
MANAGER_ROLES = (*ADMIN_ROLES, UserRole.TEACHER.value)
PASSING_STATUSES = {"PASS"}


async def _count(db: AsyncSession, query) -> int:
    return int(await query.count() or 0)


def _full_student_name(student: Student | None) -> str:
    if not student:
        return ""
    return f"{student.first_name} {student.last_name or ''}".strip()


def _loaded(obj: Any, relation_name: str):
    """
    Read only already-loaded relationships.

    In async SQLAlchemy, direct lazy access like exam.school_class.name can raise
    MissingGreenlet. Always query with joinedload/selectinload first, then read
    with this helper inside response builders.
    """
    if obj is None:
        return None
    return obj.__dict__.get(relation_name)


def _exam_load_options():
    return (
        joinedload(Exam.school_class),
        joinedload(Exam.academic_session),
    )


def _exam_subject_load_options():
    return (
        joinedload(ExamSubject.subject),
        joinedload(ExamSubject.teacher),
    )


def _student_load_options():
    return (
        joinedload(Student.school_class),
    )


def _grade_from_percentage(percentage: float | None, is_absent: bool = False) -> str:
    if is_absent:
        return "ABS"
    if percentage is None:
        return "-"
    if percentage >= 90:
        return "A+"
    if percentage >= 80:
        return "A"
    if percentage >= 70:
        return "B+"
    if percentage >= 60:
        return "B"
    if percentage >= 50:
        return "C"
    if percentage >= 40:
        return "D"
    return "F"


def _grade_from_marks(
    marks: float | None,
    max_marks: float,
    is_absent: bool = False,
) -> str:
    if is_absent:
        return "ABS"
    if marks is None or max_marks <= 0:
        return "-"
    return _grade_from_percentage(marks / max_marks * 100)


def _pass_status(
    marks: float | None,
    pass_marks: float,
    is_absent: bool = False,
) -> str:
    if is_absent:
        return "ABSENT"
    if marks is None:
        return "PENDING"
    return "PASS" if marks >= pass_marks else "FAIL"


async def _current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    today = date.today()

    active = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active.is_(True),
    ).order_by(
        AcademicSession.id.desc()
    ).first()

    if active:
        return active

    by_date = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.start_date <= today,
        AcademicSession.end_date >= today,
    ).order_by(
        AcademicSession.id.desc()
    ).first()

    if by_date:
        return by_date

    return await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id
    ).order_by(
        AcademicSession.id.desc()
    ).first()


async def _get_or_404(
    db: AsyncSession,
    model,
    item_id: int | None,
    school_id: int,
    name: str,
):
    if item_id is None:
        return None

    item = await async_query(db, model).filter(
        model.id == item_id,
        model.school_id == school_id,
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail=f"{name} not found for this school")

    return item


async def _teacher_for_user(
    db: AsyncSession,
    school_id: int,
    user: User,
    academic_session_id: int | None = None,
) -> Teacher | None:
    query = async_query(db, Teacher).filter(
        Teacher.school_id == school_id,
        Teacher.user_id == user.id,
    )
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

    query = async_query(db, Teacher).filter(
        Teacher.school_id == school_id,
        Teacher.is_active.is_(True),
        or_(*conditions),
    )
    if academic_session_id is not None:
        query = query.filter(Teacher.academic_session_id == academic_session_id)
    return await query.first()


async def _student_for_user(
    db: AsyncSession,
    school_id: int,
    user: User,
    academic_session_id: int | None = None,
) -> Student | None:
    query = async_query(db, Student).options(
        *_student_load_options()
    ).filter(
        Student.school_id == school_id,
        Student.user_id == user.id,
    )
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

    query = async_query(db, Student).options(
        *_student_load_options()
    ).filter(
        Student.school_id == school_id,
        Student.is_active.is_(True),
        or_(*conditions),
    )
    if academic_session_id is not None:
        query = query.filter(Student.academic_session_id == academic_session_id)
    return await query.first()


async def _children_for_parent(
    db: AsyncSession,
    school_id: int,
    user: User,
    academic_session_id: int | None = None,
) -> list[Student]:
    children = await children_for_parent(db, school_id, user)
    child_ids = [child.id for child in children]

    if not child_ids:
        return []

    query = async_query(db, Student).options(
        *_student_load_options()
    ).filter(
        Student.school_id == school_id,
        Student.id.in_(child_ids),
    )
    if academic_session_id is not None:
        query = query.filter(Student.academic_session_id == academic_session_id)

    return await query.order_by(
        Student.first_name.asc()
    ).all()


async def _validate_exam_scope(
    db: AsyncSession,
    school_id: int,
    class_id: int,
    section_id: int | None,
    academic_session_id: int | None,
    section_name: str | None = None,
) -> str | None:
    school_class = await _get_or_404(db, SchoolClass, class_id, school_id, "Class")
    await _get_or_404(db, AcademicSession, academic_session_id, school_id, "Academic session")

    if not school_class.is_active:
        raise HTTPException(status_code=400, detail="Selected class is inactive")

    return await validate_class_section_name(
        db,
        school_id,
        class_id,
        section_name=section_name,
        section_id=section_id,
        session_id=academic_session_id,
    )


async def _validate_exam_subject_scope(
    db: AsyncSession,
    school_id: int,
    exam: Exam,
    subject_id: int,
    teacher_id: int | None,
    max_marks: float,
    pass_marks: float,
) -> None:
    subject = await _get_or_404(db, Subject, subject_id, school_id, "Subject")
    teacher = await _get_or_404(db, Teacher, teacher_id, school_id, "Teacher")

    if subject and subject.class_id != exam.class_id:
        raise HTTPException(status_code=400, detail="Selected subject does not belong to selected exam class")

    if teacher and not teacher.is_active:
        raise HTTPException(status_code=400, detail="Selected teacher is inactive")

    if pass_marks > max_marks:
        raise HTTPException(status_code=400, detail="Pass marks cannot be greater than max marks")


def _validate_subject_schedule(
    exam: Exam,
    exam_date: date | None,
    start_time: time | None,
    end_time: time | None,
) -> None:
    if exam_date and exam.start_date and exam_date < exam.start_date:
        raise HTTPException(
            status_code=400,
            detail="Subject exam date cannot be before exam start date",
        )

    if exam_date and exam.end_date and exam_date > exam.end_date:
        raise HTTPException(
            status_code=400,
            detail="Subject exam date cannot be after exam end date",
        )

    if start_time and end_time and end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")


async def _ensure_teacher_not_double_booked(
    db: AsyncSession,
    school_id: int,
    teacher_id: int | None,
    exam_date: date | None,
    start_time: time | None,
    end_time: time | None,
    exclude_exam_subject_id: int | None = None,
) -> None:
    if not teacher_id or not exam_date or not start_time or not end_time:
        return

    query = async_query(db, ExamSubject).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.teacher_id == teacher_id,
        ExamSubject.exam_date == exam_date,
        ExamSubject.is_active.is_(True),
        ExamSubject.start_time.isnot(None),
        ExamSubject.end_time.isnot(None),
        ExamSubject.start_time < end_time,
        ExamSubject.end_time > start_time,
    )

    if exclude_exam_subject_id is not None:
        query = query.filter(ExamSubject.id != exclude_exam_subject_id)

    if await query.first():
        raise HTTPException(
            status_code=400,
            detail="This teacher is already assigned to another exam at the same time",
        )


def _clean_optional_text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _exam_date_window(exam: Exam) -> str:
    if exam.start_date and exam.end_date and exam.start_date != exam.end_date:
        return f"{format_date(exam.start_date)} to {format_date(exam.end_date)}"
    if exam.start_date:
        return format_date(exam.start_date)
    return "dates will be announced soon"


async def _notify_exam_scope(
    db: AsyncSession,
    *,
    exam: Exam,
    title: str,
    message: str,
    created_by: int | None,
    priority: str = "NORMAL",
) -> int:
    return await notify_student_scope(
        db,
        school_id=exam.school_id,
        class_id=exam.class_id,
        section_id=exam.section_id,
        academic_session_id=exam.academic_session_id,
        title=title,
        message=message,
        category="EXAM_REPORT",
        priority=priority,
        created_by=created_by,
        student_link="/student-exams",
        parent_link="/parent-exams",
    )


async def _notify_exam_subject_teacher(
    db: AsyncSession,
    *,
    exam_subject: ExamSubject,
    title: str,
    message: str,
    created_by: int | None,
    priority: str = "NORMAL",
) -> int:
    return await notify_teacher_record(
        db,
        school_id=exam_subject.school_id,
        teacher_id=exam_subject.teacher_id,
        title=title,
        message=message,
        category="EXAM_REPORT",
        priority=priority,
        created_by=created_by,
        link="/teacher-exams",
    )

async def _exam_or_404(db: AsyncSession, school_id: int, exam_id: int) -> Exam:
    exam = await async_query(db, Exam).options(
        *_exam_load_options()
    ).filter(
        Exam.school_id == school_id,
        Exam.id == exam_id,
        Exam.is_active.is_(True),
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    return exam


async def _exam_subject_or_404(
    db: AsyncSession,
    school_id: int,
    exam_subject_id: int,
    exam_id: int | None = None,
) -> ExamSubject:
    query = async_query(db, ExamSubject).options(
        *_exam_subject_load_options()
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.id == exam_subject_id,
        ExamSubject.is_active.is_(True),
    )

    if exam_id is not None:
        query = query.filter(ExamSubject.exam_id == exam_id)

    exam_subject = await query.first()

    if not exam_subject:
        raise HTTPException(status_code=404, detail="Exam subject not found")

    return exam_subject


def _students_for_exam_query(db: AsyncSession, exam: Exam):
    query = async_query(db, Student).options(
        *_student_load_options()
    ).filter(
        Student.school_id == exam.school_id,
        Student.class_id == exam.class_id,
        Student.is_active.is_(True),
    )

    if exam.academic_session_id is not None:
        query = query.filter(Student.academic_session_id == exam.academic_session_id)

    if exam.section_name:
        query = query.filter(Student.section_name == exam.section_name)
    elif exam.section_id is not None:
        query = query.filter(Student.section_id == exam.section_id)

    return query.order_by(Student.roll_number.asc(), Student.first_name.asc())


async def _exam_count_maps(
    db: AsyncSession,
    school_id: int,
    exam_ids: list[int],
) -> tuple[dict[int, int], dict[int, int]]:
    if not exam_ids:
        return {}, {}

    subject_rows = await async_query(
        db,
        ExamSubject.exam_id,
        func.count(ExamSubject.id),
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.exam_id.in_(exam_ids),
        ExamSubject.is_active.is_(True),
    ).group_by(
        ExamSubject.exam_id
    ).all()

    mark_rows = await async_query(
        db,
        ExamSubject.exam_id,
        func.count(ExamMark.id),
    ).join(
        ExamMark,
        ExamMark.exam_subject_id == ExamSubject.id,
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.exam_id.in_(exam_ids),
        ExamSubject.is_active.is_(True),
        ExamMark.school_id == school_id,
    ).group_by(
        ExamSubject.exam_id
    ).all()

    subject_counts = {int(exam_id): int(count or 0) for exam_id, count in subject_rows}
    mark_counts = {int(exam_id): int(count or 0) for exam_id, count in mark_rows}

    return subject_counts, mark_counts


async def _exam_subject_count_map(
    db: AsyncSession,
    school_id: int,
    exam_subject_ids: list[int],
) -> dict[int, int]:
    if not exam_subject_ids:
        return {}

    rows = await async_query(
        db,
        ExamMark.exam_subject_id,
        func.count(ExamMark.id),
    ).filter(
        ExamMark.school_id == school_id,
        ExamMark.exam_subject_id.in_(exam_subject_ids),
    ).group_by(
        ExamMark.exam_subject_id
    ).all()

    return {int(exam_subject_id): int(count or 0) for exam_subject_id, count in rows}


async def _exam_payload(
    db: AsyncSession,
    exam: Exam,
    subjects_count: int | None = None,
    marks_entered_count: int | None = None,
) -> ExamRead:
    if subjects_count is None or marks_entered_count is None:
        subject_counts, mark_counts = await _exam_count_maps(db, exam.school_id, [exam.id])
        subjects_count = subject_counts.get(exam.id, 0)
        marks_entered_count = mark_counts.get(exam.id, 0)

    school_class = _loaded(exam, "school_class")
    academic_session = _loaded(exam, "academic_session")

    return ExamRead(
        id=exam.id,
        name=exam.name,
        exam_type=exam.exam_type,
        description=exam.description,
        class_id=exam.class_id,
        section_id=exam.section_id,
        academic_session_id=exam.academic_session_id,
        class_name=school_class.name if school_class else None,
        section_name=exam.section_name,
        academic_session_name=academic_session.name if academic_session else None,
        start_date=exam.start_date,
        end_date=exam.end_date,
        result_status=exam.result_status,
        is_active=exam.is_active,
        subjects_count=int(subjects_count or 0),
        marks_entered_count=int(marks_entered_count or 0),
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        published_at=exam.published_at,
    )


async def _exam_payloads(db: AsyncSession, exams: list[Exam]) -> list[ExamRead]:
    exam_ids = [exam.id for exam in exams]
    subject_counts, mark_counts = await _exam_count_maps(
        db,
        exams[0].school_id if exams else 0,
        exam_ids,
    )

    return [
        await _exam_payload(
            db,
            exam,
            subjects_count=subject_counts.get(exam.id, 0),
            marks_entered_count=mark_counts.get(exam.id, 0),
        )
        for exam in exams
    ]


async def _exam_subject_payload(
    db: AsyncSession,
    item: ExamSubject,
    marks_entered_count: int | None = None,
) -> ExamSubjectRead:
    if marks_entered_count is None:
        marks_entered_count = await _count(
            db,
            async_query(db, ExamMark).filter(
                ExamMark.school_id == item.school_id,
                ExamMark.exam_subject_id == item.id,
            ),
        )

    subject = _loaded(item, "subject")
    teacher = _loaded(item, "teacher")

    return ExamSubjectRead(
        id=item.id,
        exam_id=item.exam_id,
        subject_id=item.subject_id,
        teacher_id=item.teacher_id,
        subject_name=subject.name if subject else None,
        teacher_name=teacher.full_name if teacher else None,
        max_marks=item.max_marks,
        pass_marks=item.pass_marks,
        exam_date=item.exam_date,
        start_time=item.start_time,
        end_time=item.end_time,
        room=item.room,
        timetable_note=item.timetable_note,
        is_active=item.is_active,
        marks_entered_count=int(marks_entered_count or 0),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _exam_subject_payloads(
    db: AsyncSession,
    subjects: list[ExamSubject],
) -> list[ExamSubjectRead]:
    count_map = await _exam_subject_count_map(
        db,
        subjects[0].school_id if subjects else 0,
        [subject.id for subject in subjects],
    )

    return [
        await _exam_subject_payload(
            db,
            subject,
            marks_entered_count=count_map.get(subject.id, 0),
        )
        for subject in subjects
    ]


def _mark_payload(
    student: Student,
    exam_subject: ExamSubject,
    mark: ExamMark | None,
) -> ExamMarkRead:
    return ExamMarkRead(
        id=mark.id if mark else None,
        exam_subject_id=exam_subject.id,
        student_id=student.id,
        student_name=_full_student_name(student),
        admission_no=student.admission_no,
        roll_number=student.roll_number,
        marks_obtained=mark.marks_obtained if mark else None,
        max_marks=exam_subject.max_marks,
        pass_marks=exam_subject.pass_marks,
        grade=mark.grade if mark else None,
        is_absent=bool(mark.is_absent) if mark else False,
        pass_status=mark.pass_status if mark else "PENDING",
        remarks=mark.remarks if mark else None,
        updated_at=mark.updated_at if mark else None,
    )


def _student_read(student: Student) -> ExamStudentRead:
    school_class = _loaded(student, "school_class")

    return ExamStudentRead(
        id=student.id,
        admission_no=student.admission_no,
        roll_number=student.roll_number,
        student_name=_full_student_name(student),
        class_name=school_class.name if school_class else None,
        section_name=student.section_name,
    )


def _effective_subject_date(
    exam: Exam,
    subject_index: int,
    exam_subject: ExamSubject,
) -> tuple[date | None, str]:
    if exam_subject.exam_date:
        return exam_subject.exam_date, "MANUAL"
    if exam.start_date:
        return exam.start_date + timedelta(days=subject_index), "AUTO_FROM_EXAM_START"
    return None, "NOT_SET"


def _timetable_item(
    exam: Exam,
    exam_subject: ExamSubject,
    subject_index: int,
    student: Student | None = None,
) -> ExamTimetableItem:
    effective_date, schedule_source = _effective_subject_date(
        exam,
        subject_index,
        exam_subject,
    )

    school_class = _loaded(exam, "school_class")
    subject = _loaded(exam_subject, "subject")
    teacher = _loaded(exam_subject, "teacher")

    return ExamTimetableItem(
        exam_id=exam.id,
        exam_name=exam.name,
        exam_type=exam.exam_type,
        result_status=exam.result_status,
        class_id=exam.class_id,
        section_id=exam.section_id,
        class_name=school_class.name if school_class else None,
        section_name=exam.section_name,
        start_date=exam.start_date,
        end_date=exam.end_date,
        exam_subject_id=exam_subject.id,
        subject_id=exam_subject.subject_id,
        subject_name=subject.name if subject else None,
        teacher_id=exam_subject.teacher_id,
        teacher_name=teacher.full_name if teacher else None,
        max_marks=exam_subject.max_marks,
        pass_marks=exam_subject.pass_marks,
        exam_date=effective_date,
        start_time=exam_subject.start_time,
        end_time=exam_subject.end_time,
        room=exam_subject.room,
        timetable_note=exam_subject.timetable_note,
        schedule_source=schedule_source,
        student_id=student.id if student else None,
        student_name=_full_student_name(student) if student else None,
        admission_no=student.admission_no if student else None,
        roll_number=student.roll_number if student else None,
    )


async def _exam_timetable_items_for_exam(
    db: AsyncSession,
    exam: Exam,
    student: Student | None = None,
) -> list[ExamTimetableItem]:
    subjects = await async_query(db, ExamSubject).options(
        *_exam_subject_load_options()
    ).filter(
        ExamSubject.school_id == exam.school_id,
        ExamSubject.exam_id == exam.id,
        ExamSubject.is_active.is_(True),
    ).order_by(
        ExamSubject.exam_date.asc().nullslast(),
        ExamSubject.start_time.asc().nullslast(),
        ExamSubject.id.asc(),
    ).all()

    return [
        _timetable_item(exam, exam_subject, index, student)
        for index, exam_subject in enumerate(subjects)
    ]


async def _report_cards_for_students(
    db: AsyncSession,
    exam: Exam,
    students: list[Student],
) -> list[StudentReportCard]:
    subjects = await async_query(db, ExamSubject).options(
        joinedload(ExamSubject.subject),
    ).filter(
        ExamSubject.school_id == exam.school_id,
        ExamSubject.exam_id == exam.id,
        ExamSubject.is_active.is_(True),
    ).order_by(
        ExamSubject.id.asc()
    ).all()

    if not students:
        return []

    student_ids = [student.id for student in students]
    subject_ids = [subject.id for subject in subjects]

    marks_map: dict[tuple[int, int], ExamMark] = {}
    if student_ids and subject_ids:
        marks = await async_query(db, ExamMark).filter(
            ExamMark.school_id == exam.school_id,
            ExamMark.student_id.in_(student_ids),
            ExamMark.exam_subject_id.in_(subject_ids),
        ).all()
        marks_map = {(mark.student_id, mark.exam_subject_id): mark for mark in marks}

    school_class = _loaded(exam, "school_class")

    cards: list[StudentReportCard] = []

    for student in students:
        total_marks = 0.0
        obtained = 0.0
        subject_rows: list[ReportCardSubject] = []
        has_pending = False
        has_fail = False

        for exam_subject in subjects:
            subject = _loaded(exam_subject, "subject")
            mark = marks_map.get((student.id, exam_subject.id))

            total_marks += float(exam_subject.max_marks or 0)
            marks_obtained = mark.marks_obtained if mark else None

            if marks_obtained is not None and not bool(mark.is_absent):
                obtained += float(marks_obtained)

            status_value = mark.pass_status if mark else "PENDING"

            if status_value == "PENDING":
                has_pending = True

            if status_value not in PASSING_STATUSES and status_value != "PENDING":
                has_fail = True

            subject_rows.append(
                ReportCardSubject(
                    exam_subject_id=exam_subject.id,
                    subject_id=exam_subject.subject_id,
                    subject_name=subject.name if subject else "Subject",
                    max_marks=exam_subject.max_marks,
                    pass_marks=exam_subject.pass_marks,
                    marks_obtained=marks_obtained,
                    grade=mark.grade if mark else "-",
                    is_absent=bool(mark.is_absent) if mark else False,
                    pass_status=status_value,
                    remarks=mark.remarks if mark else None,
                )
            )

        percentage = round(obtained / total_marks * 100, 2) if total_marks else 0.0
        overall_status = "PENDING" if has_pending else "FAIL" if has_fail else "PASS"

        student_class = _loaded(student, "school_class") or school_class

        cards.append(
            StudentReportCard(
                exam_id=exam.id,
                exam_name=exam.name,
                exam_type=exam.exam_type,
                result_status=exam.result_status,
                student_id=student.id,
                student_name=_full_student_name(student),
                admission_no=student.admission_no,
                roll_number=student.roll_number,
                class_name=student_class.name if student_class else None,
                section_name=student.section_name or exam.section_name,
                subjects=subject_rows,
                total_marks=round(total_marks, 2),
                marks_obtained=round(obtained, 2),
                percentage=percentage,
                grade=_grade_from_percentage(percentage),
                pass_status=overall_status,
                published_at=exam.published_at,
            )
        )

    return cards


async def _report_card_for_student(
    db: AsyncSession,
    exam: Exam,
    student: Student,
) -> StudentReportCard:
    cards = await _report_cards_for_students(db, exam, [student])
    if not cards:
        raise HTTPException(status_code=404, detail="Report card not found")
    return cards[0]


def _exam_query_for_student(db: AsyncSession, school_id: int, student: Student):
    query = async_query(db, Exam).options(
        *_exam_load_options()
    ).filter(
        Exam.school_id == school_id,
        Exam.class_id == student.class_id,
        Exam.is_active.is_(True),
        Exam.result_status == "PUBLISHED",
        or_(Exam.section_name.is_(None), Exam.section_name == student.section_name),
    )
    if student.academic_session_id is not None:
        query = query.filter(Exam.academic_session_id == student.academic_session_id)
    return query.order_by(
        Exam.start_date.desc().nullslast(),
        Exam.id.desc(),
    )


@router.get("/meta", response_model=ExamMetaResponse)
async def exam_meta(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request, current_user)

    classes_query = async_query(db, SchoolClass).filter(
        SchoolClass.school_id == school_id,
        SchoolClass.is_active.is_(True),
    )
    if session:
        classes_query = classes_query.filter(SchoolClass.academic_session_id == session.id)
    classes = await classes_query.order_by(
        SchoolClass.name.asc()
    ).all()

    subjects_query = async_query(db, Subject).filter(
        Subject.school_id == school_id,
        Subject.is_active.is_(True),
    )
    if session:
        subjects_query = subjects_query.filter(Subject.academic_session_id == session.id)
    subjects = await subjects_query.order_by(
        Subject.name.asc()
    ).all()

    teachers_query = async_query(db, Teacher).filter(
        Teacher.school_id == school_id,
        Teacher.is_active.is_(True),
    )
    if session:
        teachers_query = teachers_query.filter(Teacher.academic_session_id == session.id)
    teachers = await teachers_query.order_by(
        Teacher.full_name.asc()
    ).all()

    sessions = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id
    ).order_by(
        AcademicSession.id.desc()
    ).all()

    return ExamMetaResponse(
        classes=[ExamMetaItem(id=item.id, name=item.name) for item in classes],
        sections=[
            ExamMetaItem(id=item.id, name=item.name, extra=str(item.extra))
            for item in await class_section_options(db, school_id, session_id=session.id if session else None)
        ],
        subjects=[
            ExamMetaItem(
                id=item.id,
                name=item.name,
                extra=str(item.class_id) if item.class_id else None,
            )
            for item in subjects
        ],
        teachers=[
            ExamMetaItem(id=item.id, name=item.full_name, extra=item.employee_id)
            for item in teachers
        ],
        academic_sessions=[ExamMetaItem(id=item.id, name=item.name) for item in sessions],
        current_academic_session_id=session.id if session else None,
    )


@router.get("", response_model=list[ExamRead])
async def list_exams(
    request: Request,
    class_id: int | None = None,
    section_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    q: str = "",
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request, current_user)

    query = async_query(db, Exam).options(
        *_exam_load_options()
    ).filter(
        Exam.school_id == school_id,
        Exam.is_active.is_(True),
    )
    if session:
        query = query.filter(Exam.academic_session_id == session.id)

    if class_id:
        query = query.filter(Exam.class_id == class_id)

    if section_id and class_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session.id if session else None)
        query = query.filter(Exam.section_name == section_name)
    elif section_id:
        query = query.filter(Exam.section_id == section_id)

    if status_filter:
        query = query.filter(Exam.result_status == status_filter.upper())

    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Exam.name.ilike(like),
                Exam.exam_type.ilike(like),
                Exam.description.ilike(like),
            )
        )

    exams = await query.order_by(
        Exam.start_date.desc().nullslast(),
        Exam.id.desc(),
    ).all()

    return await _exam_payloads(db, exams)


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
async def create_exam(
    payload: ExamCreate,
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await writable_selected_academic_session(
        db, school_id, request, current_user, payload.academic_session_id
    )
    academic_session_id = session.id if session else None

    resolved_section_name = await _validate_exam_scope(
        db,
        school_id,
        payload.class_id,
        payload.section_id,
        academic_session_id,
        payload.section_name,
    )

    exam = Exam(
        school_id=school_id,
        name=payload.name.strip(),
        exam_type=(payload.exam_type or "").strip() or None,
        description=(payload.description or "").strip() or None,
        class_id=payload.class_id,
        section_id=None,
        section_name=resolved_section_name,
        academic_session_id=academic_session_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        result_status="DRAFT",
    )

    db.add(exam)
    await db.flush()
    await _notify_exam_scope(
        db,
        exam=exam,
        title='New exam scheduled',
        message=f"{exam.name} is scheduled for {_exam_date_window(exam)}.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await db.commit()
    await db.refresh(exam)

    exam = await _exam_or_404(db, school_id, exam.id)
    return await _exam_payload(db, exam)


@router.put("/{exam_id}", response_model=ExamRead)
async def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)
    data = payload.model_dump(exclude_unset=True)

    class_id = data.get("class_id", exam.class_id)
    section_id = data.get("section_id", exam.section_id)
    section_name = data.get("section_name", exam.section_name)
    academic_session_id = data.get("academic_session_id", exam.academic_session_id)
    if "academic_session_id" in data:
        await assert_academic_session_is_writable(db, school_id, academic_session_id)

    resolved_section_name = await _validate_exam_scope(db, school_id, class_id, section_id, academic_session_id, section_name)

    if "name" in data and data["name"] is not None:
        exam.name = data["name"].strip()
    if "exam_type" in data:
        exam.exam_type = (data["exam_type"] or "").strip() or None
    if "description" in data:
        exam.description = (data["description"] or "").strip() or None
    if "class_id" in data:
        exam.class_id = data["class_id"]
    if "section_id" in data or "section_name" in data or "class_id" in data:
        exam.section_id = None
        exam.section_name = resolved_section_name
    if "academic_session_id" in data:
        exam.academic_session_id = data["academic_session_id"]
    if "start_date" in data:
        exam.start_date = data["start_date"]
    if "end_date" in data:
        exam.end_date = data["end_date"]
    if "result_status" in data and data["result_status"]:
        status_value = data["result_status"].upper()
        if status_value not in {"DRAFT", "PUBLISHED"}:
            raise HTTPException(status_code=400, detail="Result status must be DRAFT or PUBLISHED")
        exam.result_status = status_value
        exam.published_at = datetime.utcnow() if status_value == "PUBLISHED" else None
    if "is_active" in data:
        exam.is_active = bool(data["is_active"])

    await _notify_exam_scope(
        db,
        exam=exam,
        title='Exam updated',
        message=f"{exam.name} details were updated. Schedule: {_exam_date_window(exam)}.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await db.commit()
    await db.refresh(exam)

    exam = await _exam_or_404(db, school_id, exam.id)
    return await _exam_payload(db, exam)


@router.delete("/{exam_id}", response_model=MessageResponse)
async def delete_exam(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)
    exam.is_active = False
    await db.commit()
    return MessageResponse(message="Exam deleted successfully")


@router.post("/{exam_id}/publish", response_model=ExamRead)
async def publish_exam(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)

    subjects_count = await _count(
        db,
        async_query(db, ExamSubject).filter(
            ExamSubject.school_id == school_id,
            ExamSubject.exam_id == exam.id,
            ExamSubject.is_active.is_(True),
        ),
    )

    if subjects_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Add at least one exam subject before publishing result",
        )

    exam.result_status = "PUBLISHED"
    exam.published_at = datetime.utcnow()
    await _notify_exam_scope(
        db,
        exam=exam,
        title='Exam result published',
        message=f"{exam.name} result has been published. Open Exam Reports to view the report card.",
        created_by=current_user.id,
        priority='HIGH',
    )
    await db.commit()
    await db.refresh(exam)

    exam = await _exam_or_404(db, school_id, exam.id)
    return await _exam_payload(db, exam)


@router.post("/{exam_id}/unpublish", response_model=ExamRead)
async def unpublish_exam(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)
    exam.result_status = "DRAFT"
    exam.published_at = None
    await db.commit()
    await db.refresh(exam)

    exam = await _exam_or_404(db, school_id, exam.id)
    return await _exam_payload(db, exam)


@router.get("/{exam_id}/subjects", response_model=list[ExamSubjectRead])
async def list_exam_subjects(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    await _exam_or_404(db, school_id, exam_id)

    rows = await async_query(db, ExamSubject).options(
        *_exam_subject_load_options()
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.exam_id == exam_id,
        ExamSubject.is_active.is_(True),
    ).order_by(
        ExamSubject.id.asc()
    ).all()

    return await _exam_subject_payloads(db, rows)


@router.get("/{exam_id}/timetable", response_model=list[ExamTimetableItem])
async def exam_timetable(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    return await _exam_timetable_items_for_exam(db, exam)


@router.post("/{exam_id}/auto-schedule-timetable", response_model=list[ExamSubjectRead])
async def auto_schedule_exam_timetable(
    exam_id: int,
    start_time: time = Query(default=time(9, 0)),
    end_time: time = Query(default=time(12, 0)),
    override_existing: bool = False,
    room: str | None = None,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)

    if not exam.start_date:
        raise HTTPException(status_code=400, detail="Set exam start date before using auto schedule")

    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    subjects = await async_query(db, ExamSubject).options(
        *_exam_subject_load_options()
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.exam_id == exam.id,
        ExamSubject.is_active.is_(True),
    ).order_by(
        ExamSubject.id.asc()
    ).all()

    if not subjects:
        raise HTTPException(status_code=400, detail="Add exam subjects before creating the timetable")

    last_auto_date = exam.start_date + timedelta(days=len(subjects) - 1)
    if exam.end_date and last_auto_date > exam.end_date:
        raise HTTPException(
            status_code=400,
            detail="Exam date range is shorter than the number of subjects. Increase end date or set subject dates manually.",
        )

    room_value = _clean_optional_text(room)

    for index, subject in enumerate(subjects):
        scheduled_date = exam.start_date + timedelta(days=index)
        should_update_date = override_existing or subject.exam_date is None
        should_update_time = override_existing or subject.start_time is None or subject.end_time is None

        new_date = scheduled_date if should_update_date else subject.exam_date
        new_start = start_time if should_update_time else subject.start_time
        new_end = end_time if should_update_time else subject.end_time

        _validate_subject_schedule(exam, new_date, new_start, new_end)
        await _ensure_teacher_not_double_booked(
            db,
            school_id,
            subject.teacher_id,
            new_date,
            new_start,
            new_end,
            exclude_exam_subject_id=subject.id,
        )

        subject.exam_date = new_date
        subject.start_time = new_start
        subject.end_time = new_end

        if room_value and (override_existing or not subject.room):
            subject.room = room_value

    await _notify_exam_scope(
        db,
        exam=exam,
        title='Exam timetable updated',
        message=f"Timetable for {exam.name} has been updated.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await db.commit()

    subjects = await async_query(db, ExamSubject).options(
        *_exam_subject_load_options()
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.exam_id == exam.id,
        ExamSubject.is_active.is_(True),
    ).order_by(
        ExamSubject.id.asc()
    ).all()

    return await _exam_subject_payloads(db, subjects)


@router.post("/{exam_id}/subjects", response_model=ExamSubjectRead, status_code=status.HTTP_201_CREATED)
async def create_exam_subject(
    exam_id: int,
    payload: ExamSubjectCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)

    await _validate_exam_subject_scope(
        db,
        school_id,
        exam,
        payload.subject_id,
        payload.teacher_id,
        payload.max_marks,
        payload.pass_marks,
    )
    _validate_subject_schedule(exam, payload.exam_date, payload.start_time, payload.end_time)
    await _ensure_teacher_not_double_booked(
        db,
        school_id,
        payload.teacher_id,
        payload.exam_date,
        payload.start_time,
        payload.end_time,
    )

    item = ExamSubject(
        school_id=school_id,
        exam_id=exam.id,
        subject_id=payload.subject_id,
        teacher_id=payload.teacher_id,
        max_marks=payload.max_marks,
        pass_marks=payload.pass_marks,
        exam_date=payload.exam_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        room=_clean_optional_text(payload.room),
        timetable_note=_clean_optional_text(payload.timetable_note),
    )

    db.add(item)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This subject is already added to the selected exam",
        )

    await _notify_exam_scope(
        db,
        exam=exam,
        title='Exam subject added',
        message=f"A subject was added to {exam.name}. Check the timetable for details.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await _notify_exam_subject_teacher(
        db,
        exam_subject=item,
        title='Exam duty assigned',
        message=f"You have been assigned to {exam.name}.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await db.commit()

    await db.refresh(item)
    item = await _exam_subject_or_404(db, school_id, item.id, exam.id)
    return await _exam_subject_payload(db, item)


@router.put("/{exam_id}/subjects/{exam_subject_id}", response_model=ExamSubjectRead)
async def update_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    payload: ExamSubjectUpdate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)
    item = await _exam_subject_or_404(db, school_id, exam_subject_id, exam_id)
    data = payload.model_dump(exclude_unset=True)

    subject_id = data.get("subject_id", item.subject_id)
    teacher_id = data.get("teacher_id", item.teacher_id)
    max_marks = data.get("max_marks", item.max_marks)
    pass_marks = data.get("pass_marks", item.pass_marks)

    await _validate_exam_subject_scope(
        db,
        school_id,
        exam,
        subject_id,
        teacher_id,
        max_marks,
        pass_marks,
    )

    exam_date = data.get("exam_date", item.exam_date)
    start_time = data.get("start_time", item.start_time)
    end_time = data.get("end_time", item.end_time)

    _validate_subject_schedule(exam, exam_date, start_time, end_time)
    await _ensure_teacher_not_double_booked(
        db,
        school_id,
        teacher_id,
        exam_date,
        start_time,
        end_time,
        exclude_exam_subject_id=item.id,
    )

    for key in [
        "subject_id",
        "teacher_id",
        "max_marks",
        "pass_marks",
        "exam_date",
        "start_time",
        "end_time",
        "is_active",
    ]:
        if key in data:
            setattr(item, key, data[key])

    if "room" in data:
        item.room = _clean_optional_text(data["room"])
    if "timetable_note" in data:
        item.timetable_note = _clean_optional_text(data["timetable_note"])

    await _notify_exam_scope(
        db,
        exam=exam,
        title='Exam subject updated',
        message=f"Subject/timetable details for {exam.name} were updated.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await _notify_exam_subject_teacher(
        db,
        exam_subject=item,
        title='Exam duty updated',
        message=f"Your exam duty for {exam.name} was updated.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await db.commit()
    await db.refresh(item)

    item = await _exam_subject_or_404(db, school_id, item.id, exam.id)
    return await _exam_subject_payload(db, item)


@router.delete("/{exam_id}/subjects/{exam_subject_id}", response_model=MessageResponse)
async def delete_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)
    item = await _exam_subject_or_404(db, school_id, exam_subject_id, exam_id)
    item.is_active = False
    await _notify_exam_scope(
        db,
        exam=exam,
        title='Exam timetable updated',
        message=f"A subject was removed from {exam.name}.",
        created_by=current_user.id,
        priority='NORMAL',
    )
    await db.commit()
    return MessageResponse(message="Exam subject removed successfully")


@router.get("/{exam_id}/students", response_model=list[ExamStudentRead])
async def list_exam_students(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    students = await _students_for_exam_query(db, exam).all()
    return [_student_read(student) for student in students]


@router.get("/{exam_id}/marks", response_model=list[ExamMarkRead])
async def list_exam_marks(
    exam_id: int,
    exam_subject_id: int = Query(...),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    exam_subject = await _exam_subject_or_404(db, school_id, exam_subject_id, exam.id)

    marks = await async_query(db, ExamMark).filter(
        ExamMark.school_id == school_id,
        ExamMark.exam_subject_id == exam_subject.id,
    ).all()
    marks_map = {mark.student_id: mark for mark in marks}

    students = await _students_for_exam_query(db, exam).all()

    return [
        _mark_payload(student, exam_subject, marks_map.get(student.id))
        for student in students
    ]


@router.post("/{exam_id}/marks/bulk", response_model=list[ExamMarkRead])
async def save_bulk_marks(
    exam_id: int,
    payload: ExamBulkMarksPayload,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    await assert_item_session_is_writable(db, school_id, exam)
    exam_subject = await _exam_subject_or_404(db, school_id, payload.exam_subject_id, exam.id)

    students = await _students_for_exam_query(db, exam).all()
    student_map = {student.id: student for student in students}
    allowed_student_ids = set(student_map)
    payload_student_ids = [row.student_id for row in payload.marks]

    existing_marks = []
    if payload_student_ids:
        existing_marks = await async_query(db, ExamMark).filter(
            ExamMark.school_id == school_id,
            ExamMark.exam_subject_id == exam_subject.id,
            ExamMark.student_id.in_(payload_student_ids),
        ).all()

    existing_map = {mark.student_id: mark for mark in existing_marks}
    saved: list[ExamMark] = []

    for row in payload.marks:
        if row.student_id not in allowed_student_ids:
            raise HTTPException(
                status_code=400,
                detail="One or more students do not belong to this exam class/section",
            )

        if row.marks_obtained is not None and row.marks_obtained > exam_subject.max_marks:
            raise HTTPException(
                status_code=400,
                detail="Marks obtained cannot be greater than max marks",
            )

        mark = existing_map.get(row.student_id)
        if not mark:
            mark = ExamMark(
                school_id=school_id,
                exam_subject_id=exam_subject.id,
                student_id=row.student_id,
            )
            db.add(mark)
            existing_map[row.student_id] = mark

        mark.is_absent = bool(row.is_absent)
        mark.marks_obtained = None if mark.is_absent else row.marks_obtained
        mark.remarks = (row.remarks or "").strip() or None
        mark.grade = _grade_from_marks(mark.marks_obtained, exam_subject.max_marks, mark.is_absent)
        mark.pass_status = _pass_status(mark.marks_obtained, exam_subject.pass_marks, mark.is_absent)
        saved.append(mark)

    if saved and exam.result_status == "PUBLISHED":
        await _notify_exam_scope(
            db,
            exam=exam,
            title='Exam marks updated',
            message=f"Marks for {exam.name} were updated. Open Exam Reports to view the latest report card.",
            created_by=current_user.id,
            priority='HIGH',
        )

    await db.commit()

    for mark in saved:
        await db.refresh(mark)

    return [
        _mark_payload(student_map[mark.student_id], exam_subject, mark)
        for mark in saved
        if mark.student_id in student_map
    ]


@router.get("/{exam_id}/class-result", response_model=ClassResultResponse)
async def class_result(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    students = await _students_for_exam_query(db, exam).all()
    results = await _report_cards_for_students(db, exam, students)

    total = len(results)
    passed = len([item for item in results if item.pass_status == "PASS"])
    failed = len([item for item in results if item.pass_status == "FAIL"])
    pending = len([item for item in results if item.pass_status == "PENDING"])
    avg_percentage = round(sum(item.percentage for item in results) / total, 2) if total else 0.0

    return ClassResultResponse(
        exam=await _exam_payload(db, exam),
        results=results,
        summary={
            "total_students": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "average_percentage": avg_percentage,
        },
    )


@router.get("/{exam_id}/subject-result/{exam_subject_id}", response_model=ExamSubjectResultRead)
async def subject_result(
    exam_id: int,
    exam_subject_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    exam = await _exam_or_404(db, school_id, exam_id)
    exam_subject = await _exam_subject_or_404(db, school_id, exam_subject_id, exam.id)

    marks = await async_query(db, ExamMark).filter(
        ExamMark.school_id == school_id,
        ExamMark.exam_subject_id == exam_subject.id,
    ).all()
    marks_map = {mark.student_id: mark for mark in marks}

    students = await _students_for_exam_query(db, exam).all()
    results = [
        _mark_payload(student, exam_subject, marks_map.get(student.id))
        for student in students
    ]

    total = len(results)
    passed = len([item for item in results if item.pass_status == "PASS"])
    failed = len([item for item in results if item.pass_status in {"FAIL", "ABSENT"}])
    pending = len([item for item in results if item.pass_status == "PENDING"])
    entered_marks = [item.marks_obtained for item in results if item.marks_obtained is not None]
    avg_marks = round(sum(entered_marks) / len(entered_marks), 2) if entered_marks else 0.0

    return ExamSubjectResultRead(
        exam=await _exam_payload(db, exam),
        exam_subject=await _exam_subject_payload(db, exam_subject),
        results=results,
        summary={
            "total_students": total,
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "average_marks": avg_marks,
        },
    )


@router.get("/my-timetable", response_model=list[ExamTimetableItem])
async def my_exam_timetable(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT.value)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request, current_user)
    student = await _student_for_user(db, school_id, current_user, session.id if session else None)
    if not student:
        return []

    exams_query = async_query(db, Exam).options(
        *_exam_load_options()
    ).filter(
        Exam.school_id == school_id,
        Exam.class_id == student.class_id,
        Exam.is_active.is_(True),
        or_(Exam.section_name.is_(None), Exam.section_name == student.section_name),
    )
    if student.academic_session_id is not None:
        exams_query = exams_query.filter(Exam.academic_session_id == student.academic_session_id)
    exams = await exams_query.order_by(
        Exam.start_date.asc().nullslast(),
        Exam.id.asc(),
    ).all()

    if not exams:
        return []

    exam_ids = [exam.id for exam in exams]
    all_subjects = await async_query(db, ExamSubject).options(
        *_exam_subject_load_options()
    ).filter(
        ExamSubject.school_id == school_id,
        ExamSubject.exam_id.in_(exam_ids),
        ExamSubject.is_active.is_(True),
    ).order_by(
        ExamSubject.exam_date.asc().nullslast(),
        ExamSubject.start_time.asc().nullslast(),
        ExamSubject.id.asc(),
    ).all()

    from collections import defaultdict

    subjects_by_exam: dict[int, list[ExamSubject]] = defaultdict(list)
    for exam_subject in all_subjects:
        subjects_by_exam[exam_subject.exam_id].append(exam_subject)

    items: list[ExamTimetableItem] = []
    for exam in exams:
        for index, exam_subject in enumerate(subjects_by_exam[exam.id]):
            items.append(_timetable_item(exam, exam_subject, index, student))

    return items


@router.get("/my-children-timetable", response_model=list[ExamTimetableItem])
async def my_children_exam_timetable(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.PARENT.value)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request, current_user)
    items: list[ExamTimetableItem] = []

    for child in await _children_for_parent(db, school_id, current_user, session.id if session else None):
        exams_query = async_query(db, Exam).options(
            *_exam_load_options()
        ).filter(
            Exam.school_id == school_id,
            Exam.class_id == child.class_id,
            Exam.is_active.is_(True),
            or_(Exam.section_name.is_(None), Exam.section_name == child.section_name),
        )
        if child.academic_session_id is not None:
            exams_query = exams_query.filter(Exam.academic_session_id == child.academic_session_id)
        exams = await exams_query.order_by(
            Exam.start_date.asc().nullslast(),
            Exam.id.asc(),
        ).all()

        for exam in exams:
            items.extend(await _exam_timetable_items_for_exam(db, exam, child))

    return items


@router.get("/my-report-cards", response_model=list[StudentReportCard])
async def my_report_cards(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT.value)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request, current_user)
    student = await _student_for_user(db, school_id, current_user, session.id if session else None)
    if not student:
        return []

    exams = await _exam_query_for_student(db, school_id, student).all()
    return [await _report_card_for_student(db, exam, student) for exam in exams]


@router.get("/my-children-report-cards", response_model=list[ParentReportCard])
async def my_children_report_cards(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.PARENT.value)),
    db: AsyncSession = Depends(get_async_db),
):
    session = await selected_academic_session(db, school_id, request, current_user)
    cards: list[ParentReportCard] = []

    for child in await _children_for_parent(db, school_id, current_user, session.id if session else None):
        exams = await _exam_query_for_student(db, school_id, child).all()
        for exam in exams:
            card = await _report_card_for_student(db, exam, child)
            cards.append(ParentReportCard(**card.model_dump()))

    return cards
