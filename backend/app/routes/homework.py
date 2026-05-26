from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Section, Subject
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.homework import (
    HomeworkAssignmentRead,
    HomeworkCheckPayload,
    HomeworkMetaItem,
    HomeworkMetaResponse,
    HomeworkSubmissionRead,
    HomeworkStats,
    ParentHomeworkRead,
    StudentHomeworkRead,
)

router = APIRouter(prefix="/homework", tags=["Phase 5 - Homework and Assignment"])

ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
MANAGER_ROLES = [UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER]
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _full_student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name or ''}".strip()


def _current_session(db: Session, school_id: int) -> AcademicSession | None:
    active = (
        db.query(AcademicSession)
        .filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True))
        .order_by(AcademicSession.id.desc())
        .first()
    )
    if active:
        return active
    return db.query(AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()


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
    conditions = [ParentGuardian.user_id == user.id]
    if user.email:
        conditions.append(ParentGuardian.email == user.email)
    if user.phone:
        conditions.append(ParentGuardian.phone == user.phone)

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


def _validate_same_school(db: Session, model, item_id: int | None, school_id: int, field_name: str):
    if item_id is None:
        return None
    item = db.query(model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{field_name} not found for this school")
    return item


def _validate_assignment_scope(db: Session, school_id: int, class_id: int, section_id: int | None, subject_id: int | None):
    school_class = _validate_same_school(db, SchoolClass, class_id, school_id, "Class")
    section = _validate_same_school(db, Section, section_id, school_id, "Section")
    subject = _validate_same_school(db, Subject, subject_id, school_id, "Subject")
    if section and section.class_id != class_id:
        raise HTTPException(status_code=400, detail="Selected section does not belong to selected class")
    if subject and subject.class_id is not None and subject.class_id != class_id:
        raise HTTPException(status_code=400, detail="Selected subject is linked to another class")
    return school_class, section, subject


def _parse_form_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Due date must be in YYYY-MM-DD format")


def _student_query_for_assignment(db: Session, assignment: HomeworkAssignment):
    query = db.query(Student).filter(
        Student.school_id == assignment.school_id,
        Student.class_id == assignment.class_id,
        Student.is_active.is_(True),
    )
    if assignment.section_id is not None:
        query = query.filter(Student.section_id == assignment.section_id)
    return query.order_by(Student.roll_number.asc(), Student.first_name.asc())


def _assignment_stats(db: Session, assignment: HomeworkAssignment) -> HomeworkStats:
    total_students = _student_query_for_assignment(db, assignment).count()
    submitted = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.school_id == assignment.school_id,
            HomeworkSubmission.homework_id == assignment.id,
            HomeworkSubmission.status == "SUBMITTED",
        )
        .count()
    )
    checked = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.school_id == assignment.school_id,
            HomeworkSubmission.homework_id == assignment.id,
            HomeworkSubmission.status == "CHECKED",
        )
        .count()
    )
    pending = max(total_students - submitted - checked, 0)
    return HomeworkStats(total_students=total_students, pending=pending, submitted=submitted, checked=checked)


def _assignment_payload(db: Session, assignment: HomeworkAssignment) -> HomeworkAssignmentRead:
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
        class_name=assignment.school_class.name if assignment.school_class else None,
        section_name=assignment.section.name if assignment.section else None,
        subject_name=assignment.subject.name if assignment.subject else None,
        teacher_name=assignment.teacher.full_name if assignment.teacher else None,
        attachment_url=assignment.attachment_url,
        attachment_filename=assignment.attachment_filename,
        is_active=assignment.is_active,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        stats=_assignment_stats(db, assignment),
    )


def _student_homework_payload(db: Session, assignment: HomeworkAssignment, student: Student) -> StudentHomeworkRead:
    submission = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.school_id == assignment.school_id,
            HomeworkSubmission.homework_id == assignment.id,
            HomeworkSubmission.student_id == student.id,
        )
        .first()
    )
    base = _assignment_payload(db, assignment).model_dump()
    return StudentHomeworkRead(
        **base,
        submission_id=submission.id if submission else None,
        submission_status=submission.status if submission else "PENDING",
        submitted_at=submission.created_at if submission else None,
        answer_text=submission.answer_text if submission else None,
        submission_attachment_url=submission.attachment_url if submission else None,
        submission_attachment_filename=submission.attachment_filename if submission else None,
        teacher_feedback=submission.teacher_feedback if submission else None,
        checked_at=submission.checked_at if submission else None,
    )


def _can_manage_assignment(db: Session, school_id: int, user: User, assignment: HomeworkAssignment) -> bool:
    if user.role in ADMIN_ROLES:
        return True
    if user.role != UserRole.TEACHER.value:
        return False
    teacher = _teacher_for_user(db, school_id, user)
    return bool(teacher and assignment.teacher_id == teacher.id)


def _get_assignment_or_404(db: Session, school_id: int, assignment_id: int) -> HomeworkAssignment:
    assignment = (
        db.query(HomeworkAssignment)
        .filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.id == assignment_id, HomeworkAssignment.is_active.is_(True))
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Homework assignment not found")
    return assignment


def _is_assignment_for_student(assignment: HomeworkAssignment, student: Student) -> bool:
    if assignment.school_id != student.school_id or assignment.class_id != student.class_id:
        return False
    return assignment.section_id is None or assignment.section_id == student.section_id


async def _save_upload(file: UploadFile | None, folder: str) -> tuple[str | None, str | None]:
    if file is None or not file.filename:
        return None, None

    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix.lower()
    content_type = file.content_type or ""

    if content_type in ALLOWED_UPLOAD_TYPES:
        suffix = ALLOWED_UPLOAD_TYPES[content_type]
    elif suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and image files are allowed")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Maximum allowed size is 10 MB")

    target_dir = UPLOAD_ROOT / "homework" / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    target_path = target_dir / stored_name
    target_path.write_bytes(data)

    return f"/uploads/homework/{folder}/{stored_name}", original_name


def _teacher_scope_hint(db: Session, school_id: int, teacher: Teacher | None) -> set[tuple[int | None, int | None]]:
    if not teacher:
        return set()
    scopes: set[tuple[int | None, int | None]] = set()
    for item in db.query(TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher.id).all():
        scopes.add((item.class_id, item.section_id))
    for item in db.query(ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id, ClassTeacherAssignment.teacher_id == teacher.id).all():
        scopes.add((item.class_id, item.section_id))
    return scopes


@router.get("/meta", response_model=HomeworkMetaResponse)
def homework_meta(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    class_query = db.query(SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True)).order_by(SchoolClass.name.asc())
    section_query = db.query(Section).filter(Section.school_id == school_id, Section.is_active.is_(True)).order_by(Section.name.asc())
    subject_query = db.query(Subject).filter(Subject.school_id == school_id, Subject.is_active.is_(True)).order_by(Subject.name.asc())

    if current_user.role == UserRole.TEACHER.value:
        teacher = _teacher_for_user(db, school_id, current_user)
        scopes = _teacher_scope_hint(db, school_id, teacher)
        class_ids = {class_id for class_id, _ in scopes if class_id is not None}
        section_ids = {section_id for _, section_id in scopes if section_id is not None}
        if class_ids:
            class_query = class_query.filter(SchoolClass.id.in_(class_ids))
            subject_query = subject_query.filter(or_(Subject.class_id.in_(class_ids), Subject.class_id.is_(None)))
        if section_ids:
            section_query = section_query.filter(Section.id.in_(section_ids))

    session = _current_session(db, school_id)
    teachers = db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True)).order_by(Teacher.full_name.asc()).all()

    return HomeworkMetaResponse(
        classes=[HomeworkMetaItem(id=item.id, name=item.name, extra=item.code) for item in class_query.all()],
        sections=[HomeworkMetaItem(id=item.id, name=item.name, extra=str(item.class_id)) for item in section_query.all()],
        subjects=[HomeworkMetaItem(id=item.id, name=item.name, extra=item.code) for item in subject_query.all()],
        teachers=[HomeworkMetaItem(id=item.id, name=item.full_name, extra=item.employee_id) for item in teachers],
        current_academic_session_id=session.id if session else None,
    )


@router.get("/assignments", response_model=list[HomeworkAssignmentRead])
def list_assignments(
    class_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    query = db.query(HomeworkAssignment).filter(HomeworkAssignment.school_id == school_id, HomeworkAssignment.is_active.is_(True))

    if current_user.role == UserRole.TEACHER.value:
        teacher = _teacher_for_user(db, school_id, current_user)
        if not teacher:
            return []
        query = query.filter(HomeworkAssignment.teacher_id == teacher.id)

    if class_id is not None:
        query = query.filter(HomeworkAssignment.class_id == class_id)
    if section_id is not None:
        query = query.filter(HomeworkAssignment.section_id == section_id)
    if subject_id is not None:
        query = query.filter(HomeworkAssignment.subject_id == subject_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(or_(HomeworkAssignment.title.ilike(like), HomeworkAssignment.description.ilike(like)))

    assignments = query.order_by(HomeworkAssignment.created_at.desc()).all()
    return [_assignment_payload(db, assignment) for assignment in assignments]


@router.post("/assignments", response_model=HomeworkAssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    title: str = Form(..., min_length=2, max_length=180),
    description: str | None = Form(default=None),
    due_date: str = Form(...),
    class_id: int = Form(...),
    section_id: int | None = Form(default=None),
    subject_id: int | None = Form(default=None),
    teacher_id: int | None = Form(default=None),
    attachment: UploadFile | None = File(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_assignment_scope(db, school_id, class_id, section_id, subject_id)
    parsed_due_date = _parse_form_date(due_date)
    session = _current_session(db, school_id)

    assigned_teacher_id = teacher_id
    if current_user.role == UserRole.TEACHER.value:
        teacher = _teacher_for_user(db, school_id, current_user)
        if not teacher:
            raise HTTPException(status_code=403, detail="Teacher profile not found for this login")
        assigned_teacher_id = teacher.id
    elif assigned_teacher_id is not None:
        _validate_same_school(db, Teacher, assigned_teacher_id, school_id, "Teacher")

    attachment_url, attachment_filename = await _save_upload(attachment, "assignments")

    assignment = HomeworkAssignment(
        school_id=school_id,
        teacher_id=assigned_teacher_id,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        academic_session_id=session.id if session else None,
        title=title.strip(),
        description=description.strip() if description else None,
        due_date=parsed_due_date,
        attachment_url=attachment_url,
        attachment_filename=attachment_filename,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_payload(db, assignment)


@router.put("/assignments/{assignment_id}", response_model=HomeworkAssignmentRead)
async def update_assignment(
    assignment_id: int,
    title: str = Form(..., min_length=2, max_length=180),
    description: str | None = Form(default=None),
    due_date: str = Form(...),
    class_id: int = Form(...),
    section_id: int | None = Form(default=None),
    subject_id: int | None = Form(default=None),
    attachment: UploadFile | None = File(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = _get_assignment_or_404(db, school_id, assignment_id)
    if not _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail="You can update only your own homework")

    _validate_assignment_scope(db, school_id, class_id, section_id, subject_id)
    assignment.title = title.strip()
    assignment.description = description.strip() if description else None
    assignment.due_date = _parse_form_date(due_date)
    assignment.class_id = class_id
    assignment.section_id = section_id
    assignment.subject_id = subject_id

    attachment_url, attachment_filename = await _save_upload(attachment, "assignments")
    if attachment_url:
        assignment.attachment_url = attachment_url
        assignment.attachment_filename = attachment_filename

    db.commit()
    db.refresh(assignment)
    return _assignment_payload(db, assignment)


@router.delete("/assignments/{assignment_id}", response_model=MessageResponse)
def delete_assignment(
    assignment_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = _get_assignment_or_404(db, school_id, assignment_id)
    if not _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail="You can delete only your own homework")
    assignment.is_active = False
    db.commit()
    return {"message": "Homework assignment deleted"}


@router.get("/assignments/{assignment_id}/submissions", response_model=list[HomeworkSubmissionRead])
def list_assignment_submissions(
    assignment_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = _get_assignment_or_404(db, school_id, assignment_id)
    if not _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail="You can view submissions only for your own homework")

    submissions = {
        item.student_id: item
        for item in db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.homework_id == assignment_id)
        .all()
    }

    rows: list[HomeworkSubmissionRead] = []
    for student in _student_query_for_assignment(db, assignment).all():
        submission = submissions.get(student.id)
        rows.append(
            HomeworkSubmissionRead(
                id=submission.id if submission else None,
                homework_id=assignment.id,
                student_id=student.id,
                student_name=_full_student_name(student),
                admission_no=student.admission_no,
                roll_number=student.roll_number,
                status=submission.status if submission else "PENDING",
                answer_text=submission.answer_text if submission else None,
                attachment_url=submission.attachment_url if submission else None,
                attachment_filename=submission.attachment_filename if submission else None,
                teacher_feedback=submission.teacher_feedback if submission else None,
                submitted_at=submission.created_at if submission else None,
                checked_at=submission.checked_at if submission else None,
            )
        )
    return rows


@router.get("/student/assignments", response_model=list[StudentHomeworkRead])
def list_student_homework(
    status_filter: str | None = Query(default=None, alias="status"),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    student = _student_for_user(db, school_id, current_user)
    if not student:
        return []

    query = db.query(HomeworkAssignment).filter(
        HomeworkAssignment.school_id == school_id,
        HomeworkAssignment.class_id == student.class_id,
        HomeworkAssignment.is_active.is_(True),
        or_(HomeworkAssignment.section_id.is_(None), HomeworkAssignment.section_id == student.section_id),
    )
    assignments = query.order_by(HomeworkAssignment.due_date.asc(), HomeworkAssignment.created_at.desc()).all()
    rows = [_student_homework_payload(db, assignment, student) for assignment in assignments]
    if status_filter:
        rows = [row for row in rows if row.submission_status == status_filter.upper()]
    return rows


@router.post("/assignments/{assignment_id}/submit", response_model=StudentHomeworkRead)
async def submit_homework(
    assignment_id: int,
    answer_text: str | None = Form(default=None),
    attachment: UploadFile | None = File(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    student = _student_for_user(db, school_id, current_user)
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found for this login")
    assignment = _get_assignment_or_404(db, school_id, assignment_id)
    if not _is_assignment_for_student(assignment, student):
        raise HTTPException(status_code=403, detail="This homework is not assigned to your class or section")

    submission = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.school_id == school_id,
            HomeworkSubmission.homework_id == assignment_id,
            HomeworkSubmission.student_id == student.id,
        )
        .first()
    )
    if not submission:
        submission = HomeworkSubmission(school_id=school_id, homework_id=assignment_id, student_id=student.id)
        db.add(submission)

    attachment_url, attachment_filename = await _save_upload(attachment, "submissions")
    submission.answer_text = answer_text.strip() if answer_text else None
    submission.status = "SUBMITTED"
    submission.teacher_feedback = None
    submission.checked_at = None
    if attachment_url:
        submission.attachment_url = attachment_url
        submission.attachment_filename = attachment_filename

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Homework already submitted. Refresh and try again")

    db.refresh(assignment)
    return _student_homework_payload(db, assignment, student)


@router.patch("/submissions/{submission_id}/check", response_model=HomeworkSubmissionRead)
def check_submission(
    submission_id: int,
    payload: HomeworkCheckPayload,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    submission = (
        db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.school_id == school_id, HomeworkSubmission.id == submission_id)
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = submission.homework
    if not assignment or not _can_manage_assignment(db, school_id, current_user, assignment):
        raise HTTPException(status_code=403, detail="You can check submissions only for your own homework")

    submission.status = "CHECKED"
    submission.teacher_feedback = payload.teacher_feedback
    submission.checked_at = datetime.utcnow()
    db.commit()
    db.refresh(submission)

    student = submission.student
    return HomeworkSubmissionRead(
        id=submission.id,
        homework_id=submission.homework_id,
        student_id=submission.student_id,
        student_name=_full_student_name(student),
        admission_no=student.admission_no,
        roll_number=student.roll_number,
        status=submission.status,
        answer_text=submission.answer_text,
        attachment_url=submission.attachment_url,
        attachment_filename=submission.attachment_filename,
        teacher_feedback=submission.teacher_feedback,
        submitted_at=submission.created_at,
        checked_at=submission.checked_at,
    )


@router.get("/parent/assignments", response_model=list[ParentHomeworkRead])
def list_parent_homework(
    child_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    children = _children_for_parent(db, school_id, current_user)
    if child_id is not None:
        children = [child for child in children if child.id == child_id]
    rows: list[ParentHomeworkRead] = []
    for child in children:
        assignments = (
            db.query(HomeworkAssignment)
            .filter(
                HomeworkAssignment.school_id == school_id,
                HomeworkAssignment.class_id == child.class_id,
                HomeworkAssignment.is_active.is_(True),
                or_(HomeworkAssignment.section_id.is_(None), HomeworkAssignment.section_id == child.section_id),
            )
            .order_by(HomeworkAssignment.due_date.asc(), HomeworkAssignment.created_at.desc())
            .all()
        )
        for assignment in assignments:
            payload = _student_homework_payload(db, assignment, child).model_dump()
            rows.append(
                ParentHomeworkRead(
                    **payload,
                    student_id=child.id,
                    student_name=_full_student_name(child),
                    admission_no=child.admission_no,
                )
            )
    return rows
