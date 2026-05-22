from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Section, Subject
from app.models.exam import Exam, ExamMark, ExamSubject
from app.models.people import ParentGuardian, Student, Teacher
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
    ExamTimetableSubject,
    ExamUpdate,
    ParentReportCard,
    ReportCardSubject,
    StudentExamTimetable,
    StudentReportCard,
)

router = APIRouter(prefix="/exams", tags=["Phase 8 - Exam and Result Management"])

ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
MANAGER_ROLES = (*ADMIN_ROLES, UserRole.TEACHER.value)
PASSING_STATUSES = {"PASS"}


def _count(db: Session, query) -> int:
    return int(query.count() or 0)


def _full_student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name or ''}".strip()


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


def _grade_from_marks(marks: float | None, max_marks: float, is_absent: bool = False) -> str:
    if is_absent:
        return "ABS"
    if marks is None or max_marks <= 0:
        return "-"
    return _grade_from_percentage((marks / max_marks) * 100)


def _pass_status(marks: float | None, pass_marks: float, is_absent: bool = False) -> str:
    if is_absent:
        return "ABSENT"
    if marks is None:
        return "PENDING"
    return "PASS" if marks >= pass_marks else "FAIL"


def _current_session(db: Session, school_id: int) -> AcademicSession | None:
    today = date.today()
    active = (
        db.query(AcademicSession)
        .filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True))
        .order_by(AcademicSession.id.desc())
        .first()
    )
    if active:
        return active
    by_date = (
        db.query(AcademicSession)
        .filter(AcademicSession.school_id == school_id, AcademicSession.start_date <= today, AcademicSession.end_date >= today)
        .order_by(AcademicSession.id.desc())
        .first()
    )
    if by_date:
        return by_date
    return db.query(AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()


def _get_or_404(db: Session, model, item_id: int | None, school_id: int, name: str):
    if item_id is None:
        return None
    item = db.query(model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{name} not found for this school")
    return item


def _teacher_for_user(db: Session, school_id: int, user: User) -> Teacher | None:
    teacher = db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.user_id == user.id).first()
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

    return db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True), or_(*conditions)).first()


def _student_for_user(db: Session, school_id: int, user: User) -> Student | None:
    student = db.query(Student).filter(Student.school_id == school_id, Student.user_id == user.id).first()
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

    return db.query(Student).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(*conditions)).first()


def _children_for_parent(db: Session, school_id: int, user: User) -> list[Student]:
    conditions = []
    if user.email:
        conditions.append(ParentGuardian.email == user.email)
    if user.phone:
        conditions.append(ParentGuardian.phone == user.phone)
    if not conditions:
        return []

    guardians = (
        db.query(ParentGuardian)
        .filter(ParentGuardian.school_id == school_id, ParentGuardian.is_active.is_(True), or_(*conditions))
        .all()
    )
    guardian_ids = [guardian.id for guardian in guardians]
    if not guardian_ids:
        return []

    return (
        db.query(Student)
        .filter(Student.school_id == school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True))
        .order_by(Student.first_name.asc())
        .all()
    )


def _validate_exam_scope(
    db: Session,
    school_id: int,
    class_id: int,
    section_id: int | None,
    academic_session_id: int | None,
) -> None:
    school_class = _get_or_404(db, SchoolClass, class_id, school_id, "Class")
    section = _get_or_404(db, Section, section_id, school_id, "Section")
    _get_or_404(db, AcademicSession, academic_session_id, school_id, "Academic session")
    if not school_class.is_active:
        raise HTTPException(status_code=400, detail="Selected class is inactive")
    if section and section.class_id != class_id:
        raise HTTPException(status_code=400, detail="Selected section does not belong to selected class")


def _validate_exam_subject_scope(db: Session, school_id: int, exam: Exam, subject_id: int, teacher_id: int | None, max_marks: float, pass_marks: float) -> None:
    subject = _get_or_404(db, Subject, subject_id, school_id, "Subject")
    teacher = _get_or_404(db, Teacher, teacher_id, school_id, "Teacher")
    if subject and subject.class_id is not None and subject.class_id != exam.class_id:
        raise HTTPException(status_code=400, detail="Selected subject is linked to another class")
    if teacher and not teacher.is_active:
        raise HTTPException(status_code=400, detail="Selected teacher is inactive")
    if pass_marks > max_marks:
        raise HTTPException(status_code=400, detail="Pass marks cannot be greater than max marks")


def _exam_or_404(db: Session, school_id: int, exam_id: int) -> Exam:
    exam = db.query(Exam).filter(Exam.school_id == school_id, Exam.id == exam_id, Exam.is_active.is_(True)).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _exam_subject_or_404(db: Session, school_id: int, exam_subject_id: int, exam_id: int | None = None) -> ExamSubject:
    query = db.query(ExamSubject).filter(ExamSubject.school_id == school_id, ExamSubject.id == exam_subject_id, ExamSubject.is_active.is_(True))
    if exam_id is not None:
        query = query.filter(ExamSubject.exam_id == exam_id)
    exam_subject = query.first()
    if not exam_subject:
        raise HTTPException(status_code=404, detail="Exam subject not found")
    return exam_subject


def _students_for_exam_query(db: Session, exam: Exam):
    query = db.query(Student).filter(
        Student.school_id == exam.school_id,
        Student.class_id == exam.class_id,
        Student.is_active.is_(True),
    )
    if exam.section_id is not None:
        query = query.filter(Student.section_id == exam.section_id)
    return query.order_by(Student.roll_number.asc(), Student.first_name.asc())


def _exam_payload(db: Session, exam: Exam) -> ExamRead:
    subjects_count = _count(db, db.query(ExamSubject).filter(ExamSubject.school_id == exam.school_id, ExamSubject.exam_id == exam.id, ExamSubject.is_active.is_(True)))
    marks_entered_count = (
        db.query(ExamMark)
        .join(ExamSubject, ExamMark.exam_subject_id == ExamSubject.id)
        .filter(ExamMark.school_id == exam.school_id, ExamSubject.exam_id == exam.id, ExamSubject.is_active.is_(True))
        .count()
    )
    return ExamRead(
        id=exam.id,
        name=exam.name,
        exam_type=exam.exam_type,
        description=exam.description,
        class_id=exam.class_id,
        section_id=exam.section_id,
        academic_session_id=exam.academic_session_id,
        class_name=exam.school_class.name if exam.school_class else None,
        section_name=exam.section.name if exam.section else None,
        academic_session_name=exam.academic_session.name if exam.academic_session else None,
        start_date=exam.start_date,
        end_date=exam.end_date,
        result_status=exam.result_status,
        is_active=exam.is_active,
        subjects_count=subjects_count,
        marks_entered_count=marks_entered_count,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        published_at=exam.published_at,
    )


def _exam_subject_payload(db: Session, item: ExamSubject) -> ExamSubjectRead:
    return ExamSubjectRead(
        id=item.id,
        exam_id=item.exam_id,
        subject_id=item.subject_id,
        teacher_id=item.teacher_id,
        subject_name=item.subject.name if item.subject else None,
        teacher_name=item.teacher.full_name if item.teacher else None,
        max_marks=item.max_marks,
        pass_marks=item.pass_marks,
        exam_date=item.exam_date,
        is_active=item.is_active,
        marks_entered_count=_count(db, db.query(ExamMark).filter(ExamMark.school_id == item.school_id, ExamMark.exam_subject_id == item.id)),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _mark_payload(student: Student, exam_subject: ExamSubject, mark: ExamMark | None) -> ExamMarkRead:
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
    return ExamStudentRead(
        id=student.id,
        admission_no=student.admission_no,
        roll_number=student.roll_number,
        student_name=_full_student_name(student),
        class_name=student.school_class.name if student.school_class else None,
        section_name=student.section.name if student.section else None,
    )


def _report_card_for_student(db: Session, exam: Exam, student: Student) -> StudentReportCard:
    subjects = (
        db.query(ExamSubject)
        .filter(ExamSubject.school_id == exam.school_id, ExamSubject.exam_id == exam.id, ExamSubject.is_active.is_(True))
        .order_by(ExamSubject.id.asc())
        .all()
    )
    total_marks = 0.0
    obtained = 0.0
    subject_rows: list[ReportCardSubject] = []
    has_pending = False
    has_fail = False

    for exam_subject in subjects:
        mark = (
            db.query(ExamMark)
            .filter(ExamMark.school_id == exam.school_id, ExamMark.exam_subject_id == exam_subject.id, ExamMark.student_id == student.id)
            .first()
        )
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
                subject_name=exam_subject.subject.name if exam_subject.subject else "Subject",
                max_marks=exam_subject.max_marks,
                pass_marks=exam_subject.pass_marks,
                marks_obtained=marks_obtained,
                grade=mark.grade if mark else "-",
                is_absent=bool(mark.is_absent) if mark else False,
                pass_status=status_value,
                remarks=mark.remarks if mark else None,
            )
        )

    percentage = round((obtained / total_marks) * 100, 2) if total_marks else 0.0
    overall_status = "PENDING" if has_pending else "FAIL" if has_fail else "PASS"

    return StudentReportCard(
        exam_id=exam.id,
        exam_name=exam.name,
        exam_type=exam.exam_type,
        result_status=exam.result_status,
        student_id=student.id,
        student_name=_full_student_name(student),
        admission_no=student.admission_no,
        roll_number=student.roll_number,
        class_name=student.school_class.name if student.school_class else None,
        section_name=student.section.name if student.section else None,
        subjects=subject_rows,
        total_marks=round(total_marks, 2),
        marks_obtained=round(obtained, 2),
        percentage=percentage,
        grade=_grade_from_percentage(percentage),
        pass_status=overall_status,
        published_at=exam.published_at,
    )


def _exam_query_for_student(db: Session, school_id: int, student: Student):
    return (
        db.query(Exam)
        .filter(
            Exam.school_id == school_id,
            Exam.class_id == student.class_id,
            Exam.is_active.is_(True),
            Exam.result_status == "PUBLISHED",
            or_(Exam.section_id.is_(None), Exam.section_id == student.section_id),
        )
        .order_by(Exam.start_date.desc().nullslast(), Exam.id.desc())
    )


def _exam_timetable_query_for_student(db: Session, school_id: int, student: Student):
    return (
        db.query(Exam)
        .filter(
            Exam.school_id == school_id,
            Exam.class_id == student.class_id,
            Exam.is_active.is_(True),
            or_(Exam.section_id.is_(None), Exam.section_id == student.section_id),
        )
        .order_by(Exam.start_date.asc().nullslast(), Exam.id.desc())
    )


def _exam_timetable_payload(db: Session, exam: Exam) -> StudentExamTimetable:
    subjects = (
        db.query(ExamSubject)
        .filter(
            ExamSubject.school_id == exam.school_id,
            ExamSubject.exam_id == exam.id,
            ExamSubject.is_active.is_(True),
        )
        .order_by(ExamSubject.exam_date.asc().nullslast(), ExamSubject.id.asc())
        .all()
    )
    return StudentExamTimetable(
        exam_id=exam.id,
        exam_name=exam.name,
        exam_type=exam.exam_type,
        description=exam.description,
        result_status=exam.result_status,
        class_name=exam.school_class.name if exam.school_class else None,
        section_name=exam.section.name if exam.section else None,
        academic_session_name=exam.academic_session.name if exam.academic_session else None,
        start_date=exam.start_date,
        end_date=exam.end_date,
        subjects=[
            ExamTimetableSubject(
                exam_subject_id=item.id,
                subject_id=item.subject_id,
                subject_name=item.subject.name if item.subject else "Subject",
                teacher_id=item.teacher_id,
                teacher_name=item.teacher.full_name if item.teacher else None,
                exam_date=item.exam_date,
                max_marks=item.max_marks,
                pass_marks=item.pass_marks,
            )
            for item in subjects
        ],
    )


@router.get("/meta", response_model=ExamMetaResponse)
def exam_meta(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    session = _current_session(db, school_id)
    classes = db.query(SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True)).order_by(SchoolClass.name.asc()).all()
    sections = db.query(Section).filter(Section.school_id == school_id, Section.is_active.is_(True)).order_by(Section.name.asc()).all()
    subjects = db.query(Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True)).order_by(Subject.name.asc()).all()
    teachers = db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True)).order_by(Teacher.full_name.asc()).all()
    sessions = db.query(AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).all()

    return ExamMetaResponse(
        classes=[ExamMetaItem(id=item.id, name=item.name) for item in classes],
        sections=[ExamMetaItem(id=item.id, name=item.name, extra=str(item.class_id)) for item in sections],
        subjects=[ExamMetaItem(id=item.id, name=item.name, extra=str(item.class_id) if item.class_id else None) for item in subjects],
        teachers=[ExamMetaItem(id=item.id, name=item.full_name, extra=item.employee_id) for item in teachers],
        academic_sessions=[ExamMetaItem(id=item.id, name=item.name) for item in sessions],
        current_academic_session_id=session.id if session else None,
    )


@router.get("", response_model=list[ExamRead])
def list_exams(
    class_id: int | None = None,
    section_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    q: str = "",
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    query = db.query(Exam).filter(Exam.school_id == school_id, Exam.is_active.is_(True))
    if class_id:
        query = query.filter(Exam.class_id == class_id)
    if section_id:
        query = query.filter(Exam.section_id == section_id)
    if status_filter:
        query = query.filter(Exam.result_status == status_filter.upper())
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Exam.name.ilike(like), Exam.exam_type.ilike(like), Exam.description.ilike(like)))
    exams = query.order_by(Exam.start_date.desc().nullslast(), Exam.id.desc()).all()
    return [_exam_payload(db, exam) for exam in exams]


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_exam_scope(db, school_id, payload.class_id, payload.section_id, payload.academic_session_id)
    exam = Exam(
        school_id=school_id,
        name=payload.name.strip(),
        exam_type=(payload.exam_type or "").strip() or None,
        description=(payload.description or "").strip() or None,
        class_id=payload.class_id,
        section_id=payload.section_id,
        academic_session_id=payload.academic_session_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        result_status="DRAFT",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _exam_payload(db, exam)


@router.put("/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    data = payload.model_dump(exclude_unset=True)
    class_id = data.get("class_id", exam.class_id)
    section_id = data.get("section_id", exam.section_id)
    academic_session_id = data.get("academic_session_id", exam.academic_session_id)
    _validate_exam_scope(db, school_id, class_id, section_id, academic_session_id)

    if "name" in data and data["name"] is not None:
        exam.name = data["name"].strip()
    if "exam_type" in data:
        exam.exam_type = (data["exam_type"] or "").strip() or None
    if "description" in data:
        exam.description = (data["description"] or "").strip() or None
    if "class_id" in data:
        exam.class_id = data["class_id"]
    if "section_id" in data:
        exam.section_id = data["section_id"]
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

    db.commit()
    db.refresh(exam)
    return _exam_payload(db, exam)


@router.delete("/{exam_id}", response_model=MessageResponse)
def delete_exam(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    exam.is_active = False
    db.commit()
    return MessageResponse(message="Exam deleted successfully")


@router.post("/{exam_id}/publish", response_model=ExamRead)
def publish_exam(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    subjects_count = _count(db, db.query(ExamSubject).filter(ExamSubject.school_id == school_id, ExamSubject.exam_id == exam.id, ExamSubject.is_active.is_(True)))
    if subjects_count == 0:
        raise HTTPException(status_code=400, detail="Add at least one exam subject before publishing result")
    exam.result_status = "PUBLISHED"
    exam.published_at = datetime.utcnow()
    db.commit()
    db.refresh(exam)
    return _exam_payload(db, exam)


@router.post("/{exam_id}/unpublish", response_model=ExamRead)
def unpublish_exam(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    exam.result_status = "DRAFT"
    exam.published_at = None
    db.commit()
    db.refresh(exam)
    return _exam_payload(db, exam)


@router.get("/{exam_id}/subjects", response_model=list[ExamSubjectRead])
def list_exam_subjects(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    _exam_or_404(db, school_id, exam_id)
    rows = db.query(ExamSubject).filter(ExamSubject.school_id == school_id, ExamSubject.exam_id == exam_id, ExamSubject.is_active.is_(True)).order_by(ExamSubject.id.asc()).all()
    return [_exam_subject_payload(db, item) for item in rows]


@router.post("/{exam_id}/subjects", response_model=ExamSubjectRead, status_code=status.HTTP_201_CREATED)
def create_exam_subject(
    exam_id: int,
    payload: ExamSubjectCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    _validate_exam_subject_scope(db, school_id, exam, payload.subject_id, payload.teacher_id, payload.max_marks, payload.pass_marks)
    item = ExamSubject(
        school_id=school_id,
        exam_id=exam.id,
        subject_id=payload.subject_id,
        teacher_id=payload.teacher_id,
        max_marks=payload.max_marks,
        pass_marks=payload.pass_marks,
        exam_date=payload.exam_date,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="This subject is already added to the selected exam")
    db.refresh(item)
    return _exam_subject_payload(db, item)


@router.put("/{exam_id}/subjects/{exam_subject_id}", response_model=ExamSubjectRead)
def update_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    payload: ExamSubjectUpdate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    item = _exam_subject_or_404(db, school_id, exam_subject_id, exam_id)
    data = payload.model_dump(exclude_unset=True)
    subject_id = data.get("subject_id", item.subject_id)
    teacher_id = data.get("teacher_id", item.teacher_id)
    max_marks = data.get("max_marks", item.max_marks)
    pass_marks = data.get("pass_marks", item.pass_marks)
    _validate_exam_subject_scope(db, school_id, exam, subject_id, teacher_id, max_marks, pass_marks)

    for key in ["subject_id", "teacher_id", "max_marks", "pass_marks", "exam_date", "is_active"]:
        if key in data:
            setattr(item, key, data[key])
    db.commit()
    db.refresh(item)
    return _exam_subject_payload(db, item)


@router.delete("/{exam_id}/subjects/{exam_subject_id}", response_model=MessageResponse)
def delete_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    _exam_or_404(db, school_id, exam_id)
    item = _exam_subject_or_404(db, school_id, exam_subject_id, exam_id)
    item.is_active = False
    db.commit()
    return MessageResponse(message="Exam subject removed successfully")


@router.get("/{exam_id}/students", response_model=list[ExamStudentRead])
def list_exam_students(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    return [_student_read(student) for student in _students_for_exam_query(db, exam).all()]


@router.get("/{exam_id}/marks", response_model=list[ExamMarkRead])
def list_exam_marks(
    exam_id: int,
    exam_subject_id: int = Query(...),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    exam_subject = _exam_subject_or_404(db, school_id, exam_subject_id, exam.id)
    marks = {
        mark.student_id: mark
        for mark in db.query(ExamMark).filter(ExamMark.school_id == school_id, ExamMark.exam_subject_id == exam_subject.id).all()
    }
    return [_mark_payload(student, exam_subject, marks.get(student.id)) for student in _students_for_exam_query(db, exam).all()]


@router.post("/{exam_id}/marks/bulk", response_model=list[ExamMarkRead])
def save_bulk_marks(
    exam_id: int,
    payload: ExamBulkMarksPayload,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    exam_subject = _exam_subject_or_404(db, school_id, payload.exam_subject_id, exam.id)
    allowed_student_ids = {student.id for student in _students_for_exam_query(db, exam).all()}
    saved: list[ExamMark] = []

    for row in payload.marks:
        if row.student_id not in allowed_student_ids:
            raise HTTPException(status_code=400, detail="One or more students do not belong to this exam class/section")
        if row.marks_obtained is not None and row.marks_obtained > exam_subject.max_marks:
            raise HTTPException(status_code=400, detail="Marks obtained cannot be greater than max marks")

        mark = (
            db.query(ExamMark)
            .filter(ExamMark.school_id == school_id, ExamMark.exam_subject_id == exam_subject.id, ExamMark.student_id == row.student_id)
            .first()
        )
        if not mark:
            mark = ExamMark(school_id=school_id, exam_subject_id=exam_subject.id, student_id=row.student_id)
            db.add(mark)

        mark.is_absent = bool(row.is_absent)
        mark.marks_obtained = None if mark.is_absent else row.marks_obtained
        mark.remarks = (row.remarks or "").strip() or None
        mark.grade = _grade_from_marks(mark.marks_obtained, exam_subject.max_marks, mark.is_absent)
        mark.pass_status = _pass_status(mark.marks_obtained, exam_subject.pass_marks, mark.is_absent)
        saved.append(mark)

    db.commit()
    for mark in saved:
        db.refresh(mark)

    students = {student.id: student for student in _students_for_exam_query(db, exam).all()}
    return [_mark_payload(students[mark.student_id], exam_subject, mark) for mark in saved if mark.student_id in students]


@router.get("/{exam_id}/class-result", response_model=ClassResultResponse)
def class_result(
    exam_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    results = [_report_card_for_student(db, exam, student) for student in _students_for_exam_query(db, exam).all()]
    total = len(results)
    passed = len([item for item in results if item.pass_status == "PASS"])
    failed = len([item for item in results if item.pass_status == "FAIL"])
    pending = len([item for item in results if item.pass_status == "PENDING"])
    avg_percentage = round(sum(item.percentage for item in results) / total, 2) if total else 0.0
    return ClassResultResponse(
        exam=_exam_payload(db, exam),
        results=results,
        summary={"total_students": total, "passed": passed, "failed": failed, "pending": pending, "average_percentage": avg_percentage},
    )


@router.get("/{exam_id}/subject-result/{exam_subject_id}", response_model=ExamSubjectResultRead)
def subject_result(
    exam_id: int,
    exam_subject_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    exam = _exam_or_404(db, school_id, exam_id)
    exam_subject = _exam_subject_or_404(db, school_id, exam_subject_id, exam.id)
    marks = {
        mark.student_id: mark
        for mark in db.query(ExamMark).filter(ExamMark.school_id == school_id, ExamMark.exam_subject_id == exam_subject.id).all()
    }
    results = [_mark_payload(student, exam_subject, marks.get(student.id)) for student in _students_for_exam_query(db, exam).all()]
    total = len(results)
    passed = len([item for item in results if item.pass_status == "PASS"])
    failed = len([item for item in results if item.pass_status in {"FAIL", "ABSENT"}])
    pending = len([item for item in results if item.pass_status == "PENDING"])
    entered_marks = [item.marks_obtained for item in results if item.marks_obtained is not None]
    avg_marks = round(sum(entered_marks) / len(entered_marks), 2) if entered_marks else 0.0
    return ExamSubjectResultRead(
        exam=_exam_payload(db, exam),
        exam_subject=_exam_subject_payload(db, exam_subject),
        results=results,
        summary={"total_students": total, "passed": passed, "failed": failed, "pending": pending, "average_marks": avg_marks},
    )


@router.get("/my-timetable", response_model=list[StudentExamTimetable])
def my_exam_timetable(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT.value)),
    db: Session = Depends(get_db),
):
    student = _student_for_user(db, school_id, current_user)
    if not student:
        return []
    exams = _exam_timetable_query_for_student(db, school_id, student).all()
    return [_exam_timetable_payload(db, exam) for exam in exams]


@router.get("/my-report-cards", response_model=list[StudentReportCard])
def my_report_cards(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT.value)),
    db: Session = Depends(get_db),
):
    student = _student_for_user(db, school_id, current_user)
    if not student:
        return []
    exams = _exam_query_for_student(db, school_id, student).all()
    return [_report_card_for_student(db, exam, student) for exam in exams]


@router.get("/my-children-report-cards", response_model=list[ParentReportCard])
def my_children_report_cards(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.PARENT.value)),
    db: Session = Depends(get_db),
):
    cards: list[ParentReportCard] = []
    for child in _children_for_parent(db, school_id, current_user):
        for exam in _exam_query_for_student(db, school_id, child).all():
            cards.append(ParentReportCard(**_report_card_for_student(db, exam, child).model_dump()))
    return cards
