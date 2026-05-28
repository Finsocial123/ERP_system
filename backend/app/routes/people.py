from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.schemas.meetings import TeacherClassOut
from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.utils import generate_temporary_password, normalize_login_id
from app.dependencies.auth import current_school_id, require_school_admin, get_current_user
from app.models.academic import AcademicSession, Department, SchoolClass, Section, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.people import (
    ClassTeacherCreate,
    ClassTeacherRead,
    ParentLoginCreate,
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TeacherCreate,
    TeacherRead,
    TeacherSubjectCreate,
    TeacherSubjectRead,
    TeacherUpdate,
)

router = APIRouter(tags=["Phase 2 - Student and Teacher Management"])


def _get_or_404(db: Session, model, item_id: int, school_id: int):
    item = db.query(model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def _validate_same_school(db: Session, model, item_id: int | None, school_id: int, field_name: str):
    if item_id is None:
        return None
    item = db.query(model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{field_name} not found for this school")
    return item


def _validate_section_belongs_to_class(db: Session, section_id: int | None, class_id: int | None, school_id: int):
    if section_id is None:
        return
    section = _validate_same_school(db, Section, section_id, school_id, "Section")
    if class_id is not None and section.class_id != class_id:
        raise HTTPException(status_code=400, detail="Selected section does not belong to selected class")


def _commit_or_duplicate(db: Session, duplicate_message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=duplicate_message)


def _school_slug(db: Session, school_id: int) -> str:
    school = db.get(School, school_id)
    return school.slug if school else f"school-{school_id}"


def _synthetic_email(login_id: str, school_slug: str, role: str) -> str:
    safe_id = normalize_login_id(login_id).lower().replace("@", "-")
    return f"{safe_id}@{school_slug}.{role.lower()}.local"


def _ensure_login_id_available(db: Session, school_id: int, login_id: str, exclude_user_id: int | None = None):
    normalized = normalize_login_id(login_id)
    query = db.query(User).filter(User.school_id == school_id, User.login_id == normalized)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise HTTPException(status_code=409, detail="A user with this login ID already exists in this school")
    return normalized


def _parent_login_candidates(guardian: ParentGuardian, fallback_seed: str) -> list[str]:
    """Build safe parent login candidates.

    Do not use phone number as a parent login identifier. In demo/real data,
    many guardians can share a placeholder or family phone number, and using it
    can wrongly link multiple guardians to the same parent user.
    """
    candidates: list[str] = []
    for value in (guardian.email, f"{fallback_seed}-PARENT", f"PARENT-{fallback_seed}"):
        if value and str(value).strip():
            normalized = normalize_login_id(str(value))
            if normalized and normalized not in candidates:
                candidates.append(normalized)
    return candidates


def _ensure_parent_login(
    db: Session,
    school_id: int,
    guardian: ParentGuardian,
    fallback_seed: str,
    password: str | None = None,
) -> tuple[User | None, str | None]:
    """Create or link a parent portal user for a guardian.

    Returns (user, temporary_password). temporary_password is only returned when a
    new login is created. If a matching parent user already exists, the guardian
    is linked to it without changing that user's password.
    """
    if guardian.user_id:
        return db.get(User, guardian.user_id), None

    school_slug = _school_slug(db, school_id)
    candidate_login_ids = _parent_login_candidates(guardian, fallback_seed)
    if guardian.id:
        candidate_login_ids.append(normalize_login_id(f"{fallback_seed}-PARENT-{guardian.id}"))

    selected_login_id: str | None = None
    for login_id in candidate_login_ids:
        existing = db.query(User).filter(User.school_id == school_id, User.login_id == login_id).first()
        if not existing:
            selected_login_id = login_id
            break
        if existing.role == UserRole.PARENT.value:
            guardian.user_id = existing.id
            return existing, None

    if not selected_login_id:
        selected_login_id = normalize_login_id(f"PARENT-{fallback_seed}-{guardian.id or 'NEW'}")
        suffix = 1
        base_login_id = selected_login_id
        while db.query(User).filter(User.school_id == school_id, User.login_id == selected_login_id).first():
            suffix += 1
            selected_login_id = normalize_login_id(f"{base_login_id}-{suffix}")

    temporary_password = password or generate_temporary_password()
    user = User(
        school_id=school_id,
        full_name=guardian.full_name,
        email=str(guardian.email).lower() if guardian.email else _synthetic_email(selected_login_id, school_slug, "parent"),
        phone=guardian.phone,
        login_id=selected_login_id,
        hashed_password=get_password_hash(temporary_password),
        role=UserRole.PARENT.value,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    guardian.user_id = user.id
    return user, temporary_password


# Students
@router.get("/students", response_model=list[StudentRead])
def list_students(
    search: str | None = Query(default=None),
    class_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    school_id: int = Depends(current_school_id),
    db: Session = Depends(get_db),
):
    query = db.query(Student).filter(Student.school_id == school_id, Student.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Student.first_name.ilike(like),
                Student.last_name.ilike(like),
                Student.admission_no.ilike(like),
                Student.roll_number.ilike(like),
                Student.email.ilike(like),
            )
        )
    if class_id is not None:
        query = query.filter(Student.class_id == class_id)
    if section_id is not None:
        query = query.filter(Student.section_id == section_id)
    if status_value:
        query = query.filter(Student.status == status_value.upper())
    return query.order_by(Student.id.desc()).all()


@router.post("/students", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    school_id = current_user.school_id
    _validate_same_school(db, SchoolClass, payload.class_id, school_id, "Class")
    _validate_same_school(db, Section, payload.section_id, school_id, "Section")
    _validate_section_belongs_to_class(db, payload.section_id, payload.class_id, school_id)

    if payload.create_parent_login and not payload.guardian:
        raise HTTPException(status_code=400, detail="Add parent/guardian details before creating a parent login")

    guardian = None
    parent_temporary_password = None
    if payload.guardian:
        guardian = ParentGuardian(school_id=school_id, **payload.guardian.model_dump(exclude_none=True))
        db.add(guardian)
        db.flush()
        if payload.create_parent_login:
            parent_user, parent_temporary_password = _ensure_parent_login(db, school_id, guardian, payload.admission_no, payload.parent_password)

    user_id = None
    temporary_password = None
    if payload.create_login:
        login_id = _ensure_login_id_available(db, school_id, payload.admission_no)
        temporary_password = payload.password or generate_temporary_password()
        full_name = f"{payload.first_name} {payload.last_name or ''}".strip()
        school_slug = _school_slug(db, school_id)
        user = User(
            school_id=school_id,
            full_name=full_name,
            email=str(payload.email).lower() if payload.email else _synthetic_email(payload.admission_no, school_slug, "student"),
            phone=payload.phone,
            login_id=login_id,
            hashed_password=get_password_hash(temporary_password),
            role=UserRole.STUDENT.value,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id

    data = payload.model_dump(exclude={"guardian", "create_login", "password", "create_parent_login", "parent_password"})
    student = Student(school_id=school_id, guardian_id=guardian.id if guardian else None, user_id=user_id, **data)
    db.add(student)
    _commit_or_duplicate(db, "Student admission number already exists in this school")
    db.refresh(student)
    student.temporary_password = temporary_password
    student.parent_temporary_password = parent_temporary_password
    if guardian and guardian.user:
        student.parent_login_id = guardian.user.login_id
    elif guardian and guardian.user_id:
        parent_user = db.get(User, guardian.user_id)
        student.parent_login_id = parent_user.login_id if parent_user else None
    return student


@router.get("/students/{student_id}", response_model=StudentRead)
def get_student(student_id: int, school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    return _get_or_404(db, Student, student_id, school_id)




@router.post("/students/{student_id}/parent-login", response_model=StudentRead)
def create_parent_login_for_student(
    student_id: int,
    payload: ParentLoginCreate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school_id = current_user.school_id
    student = _get_or_404(db, Student, student_id, school_id)
    if not student.guardian:
        raise HTTPException(status_code=400, detail="This student has no parent/guardian details")

    parent_user, temporary_password = _ensure_parent_login(db, school_id, student.guardian, student.admission_no, payload.password)
    db.commit()
    db.refresh(student)
    student.parent_temporary_password = temporary_password
    student.parent_login_id = parent_user.login_id if parent_user else None
    return student


@router.put("/students/{student_id}", response_model=StudentRead)
def update_student(student_id: int, payload: StudentUpdate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    school_id = current_user.school_id
    student = _get_or_404(db, Student, student_id, school_id)
    values = payload.model_dump(exclude_unset=True, exclude={"guardian", "create_parent_login", "parent_password"})

    class_id = values.get("class_id", student.class_id)
    section_id = values.get("section_id", student.section_id)
    if "class_id" in values:
        _validate_same_school(db, SchoolClass, values.get("class_id"), school_id, "Class")
    if "section_id" in values:
        _validate_same_school(db, Section, values.get("section_id"), school_id, "Section")
    _validate_section_belongs_to_class(db, section_id, class_id, school_id)

    if "admission_no" in values and student.user_id:
        _ensure_login_id_available(db, school_id, values["admission_no"], exclude_user_id=student.user_id)

    for key, value in values.items():
        setattr(student, key, value)

    parent_temporary_password = None
    if payload.guardian is not None:
        guardian_values = payload.guardian.model_dump(exclude_unset=True)
        if student.guardian:
            for key, value in guardian_values.items():
                setattr(student.guardian, key, value)
        elif guardian_values.get("full_name"):
            guardian = ParentGuardian(school_id=school_id, **guardian_values)
            db.add(guardian)
            db.flush()
            student.guardian_id = guardian.id

    if payload.create_parent_login:
        if not student.guardian:
            raise HTTPException(status_code=400, detail="Add parent/guardian details before creating a parent login")
        parent_user, parent_temporary_password = _ensure_parent_login(db, school_id, student.guardian, student.admission_no, payload.parent_password)

    if student.user_id:
        user = db.get(User, student.user_id)
        if user:
            user.full_name = f"{student.first_name} {student.last_name or ''}".strip()
            user.phone = student.phone
            user.login_id = normalize_login_id(student.admission_no)
            if student.email:
                user.email = str(student.email).lower()
            user.is_active = student.is_active

    _commit_or_duplicate(db, "Student admission number already exists in this school")
    db.refresh(student)
    student.parent_temporary_password = parent_temporary_password
    if payload.create_parent_login:
        if student.guardian and student.guardian.user:
            student.parent_login_id = student.guardian.user.login_id
        elif student.guardian and student.guardian.user_id:
            parent_user = db.get(User, student.guardian.user_id)
            student.parent_login_id = parent_user.login_id if parent_user else None
    return student


@router.patch("/students/{student_id}/suspend", response_model=StudentRead)
def suspend_student(student_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    student = _get_or_404(db, Student, student_id, current_user.school_id)
    student.status = "SUSPENDED"
    student.is_active = False
    if student.user_id:
        user = db.get(User, student.user_id)
        if user:
            user.is_active = False
    db.commit()
    db.refresh(student)
    return student


@router.patch("/students/{student_id}/activate", response_model=StudentRead)
def activate_student(student_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    student = _get_or_404(db, Student, student_id, current_user.school_id)
    student.status = "ACTIVE"
    student.is_active = True
    if student.user_id:
        user = db.get(User, student.user_id)
        if user:
            user.is_active = True
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}", response_model=MessageResponse)
def delete_student(student_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    student = _get_or_404(db, Student, student_id, current_user.school_id)
    student.status = "DELETED"
    student.is_active = False
    if student.user_id:
        user = db.get(User, student.user_id)
        if user:
            user.is_active = False
    db.commit()
    return {"message": "Student deactivated"}


# Teachers
@router.get("/teachers", response_model=list[TeacherRead])
def list_teachers(
    search: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    school_id: int = Depends(current_school_id),
    db: Session = Depends(get_db),
):
    query = db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(Teacher.full_name.ilike(like), Teacher.employee_id.ilike(like), Teacher.email.ilike(like), Teacher.phone.ilike(like))
        )
    if department_id is not None:
        query = query.filter(Teacher.department_id == department_id)
    if status_value:
        query = query.filter(Teacher.status == status_value.upper())
    return query.order_by(Teacher.id.desc()).all()


@router.post("/teachers", response_model=TeacherRead, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    school_id = current_user.school_id
    _validate_same_school(db, Department, payload.department_id, school_id, "Department")

    user_id = None
    temporary_password = None
    if payload.create_login:
        login_id = _ensure_login_id_available(db, school_id, payload.employee_id)
        temporary_password = payload.password or generate_temporary_password()
        school_slug = _school_slug(db, school_id)
        user = User(
            school_id=school_id,
            full_name=payload.full_name,
            email=str(payload.email).lower() if payload.email else _synthetic_email(payload.employee_id, school_slug, "teacher"),
            phone=payload.phone,
            login_id=login_id,
            hashed_password=get_password_hash(temporary_password),
            role=UserRole.TEACHER.value,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id

    data = payload.model_dump(exclude={"create_login", "password"})
    teacher = Teacher(school_id=school_id, user_id=user_id, **data)
    db.add(teacher)
    _commit_or_duplicate(db, "Teacher employee ID already exists in this school")
    db.refresh(teacher)
    teacher.temporary_password = temporary_password
    return teacher


# Class teacher assignment
@router.get("/teachers/class-teachers", response_model=list[ClassTeacherRead])
def list_class_teachers(school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    return db.query(ClassTeacherAssignment).filter(ClassTeacherAssignment.school_id == school_id).order_by(ClassTeacherAssignment.id.desc()).all()


@router.post("/teachers/class-teachers", response_model=ClassTeacherRead, status_code=status.HTTP_201_CREATED)
def assign_class_teacher(payload: ClassTeacherCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    school_id = current_user.school_id
    _get_or_404(db, Teacher, payload.teacher_id, school_id)
    _validate_same_school(db, SchoolClass, payload.class_id, school_id, "Class")
    _validate_same_school(db, Section, payload.section_id, school_id, "Section")
    _validate_same_school(db, AcademicSession, payload.academic_session_id, school_id, "Academic session")
    _validate_section_belongs_to_class(db, payload.section_id, payload.class_id, school_id)

    assignment = ClassTeacherAssignment(school_id=school_id, **payload.model_dump())
    db.add(assignment)
    _commit_or_duplicate(db, "This class already has a class teacher for the selected session")
    db.refresh(assignment)
    return assignment


@router.delete("/teachers/class-teachers/{assignment_id}", response_model=MessageResponse)
def delete_class_teacher_assignment(assignment_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    assignment = _get_or_404(db, ClassTeacherAssignment, assignment_id, current_user.school_id)
    db.delete(assignment)
    db.commit()
    return {"message": "Class teacher assignment removed"}



@router.delete("/teachers/subject-assignments/{assignment_id}", response_model=MessageResponse)
def delete_teacher_subject_assignment(assignment_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    assignment = _get_or_404(db, TeacherSubject, assignment_id, current_user.school_id)
    db.delete(assignment)
    db.commit()
    return {"message": "Teacher subject assignment removed"}


@router.get("/teachers/me/classes", response_model=list[TeacherClassOut])
def get_my_classes(
    current_user: User = Depends(get_current_user),
    school_id: int = Depends(current_school_id),
    db: Session = Depends(get_db),
):
    teacher = (
        db.query(Teacher)
        .filter(
            Teacher.user_id == current_user.id,
            Teacher.school_id == school_id,
            Teacher.is_active.is_(True),
        )
        .first()
    )
    if not teacher:
        raise HTTPException(404, "No teacher profile found for this user")

    assignments = (
        db.query(TeacherSubject)
        .filter(
            TeacherSubject.teacher_id == teacher.id,
            TeacherSubject.school_id == school_id,
        )
        .order_by(TeacherSubject.class_id, TeacherSubject.section_id)
        .all()
    )

    return [
        {
            "class_id":     a.class_id,
            "class_name":   a.school_class.name if a.school_class else f"Class {a.class_id}",
            "section_id":   a.section_id,
            "section_name": a.section.name if a.section else None,
            "subject_id":   a.subject_id,
            "subject_name": a.subject.name if a.subject else f"Subject {a.subject_id}",
        }
        for a in assignments
    ]







@router.get("/teachers/{teacher_id}", response_model=TeacherRead)
def get_teacher(teacher_id: int, school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    return _get_or_404(db, Teacher, teacher_id, school_id)


@router.put("/teachers/{teacher_id}", response_model=TeacherRead)
def update_teacher(teacher_id: int, payload: TeacherUpdate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    school_id = current_user.school_id
    teacher = _get_or_404(db, Teacher, teacher_id, school_id)
    values = payload.model_dump(exclude_unset=True)
    if "department_id" in values:
        _validate_same_school(db, Department, values.get("department_id"), school_id, "Department")
    if "employee_id" in values and teacher.user_id:
        _ensure_login_id_available(db, school_id, values["employee_id"], exclude_user_id=teacher.user_id)

    for key, value in values.items():
        setattr(teacher, key, value)

    if teacher.user_id:
        user = db.get(User, teacher.user_id)
        if user:
            user.full_name = teacher.full_name
            user.phone = teacher.phone
            user.login_id = normalize_login_id(teacher.employee_id)
            if teacher.email:
                user.email = str(teacher.email).lower()
            user.is_active = teacher.is_active

    _commit_or_duplicate(db, "Teacher employee ID already exists in this school")
    db.refresh(teacher)
    return teacher


@router.patch("/teachers/{teacher_id}/suspend", response_model=TeacherRead)
def suspend_teacher(teacher_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    teacher = _get_or_404(db, Teacher, teacher_id, current_user.school_id)
    teacher.status = "SUSPENDED"
    teacher.is_active = False
    if teacher.user_id:
        user = db.get(User, teacher.user_id)
        if user:
            user.is_active = False
    db.commit()
    db.refresh(teacher)
    return teacher


@router.patch("/teachers/{teacher_id}/activate", response_model=TeacherRead)
def activate_teacher(teacher_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    teacher = _get_or_404(db, Teacher, teacher_id, current_user.school_id)
    teacher.status = "ACTIVE"
    teacher.is_active = True
    if teacher.user_id:
        user = db.get(User, teacher.user_id)
        if user:
            user.is_active = True
    db.commit()
    db.refresh(teacher)
    return teacher

# app/routes/teachers.py
# Place this after /teachers/subject-assignments/{id} and before /teachers/{teacher_id}


@router.delete("/teachers/{teacher_id}", response_model=MessageResponse)
def delete_teacher(teacher_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    teacher = _get_or_404(db, Teacher, teacher_id, current_user.school_id)
    teacher.status = "DELETED"
    teacher.is_active = False
    if teacher.user_id:
        user = db.get(User, teacher.user_id)
        if user:
            user.is_active = False
    db.commit()
    return {"message": "Teacher deactivated"}


# Teacher subject assignment
@router.get("/teachers/{teacher_id}/subjects", response_model=list[TeacherSubjectRead])
def list_teacher_subjects(teacher_id: int, school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    _get_or_404(db, Teacher, teacher_id, school_id)
    return db.query(TeacherSubject).filter(TeacherSubject.school_id == school_id, TeacherSubject.teacher_id == teacher_id).order_by(TeacherSubject.id.desc()).all()


@router.post("/teachers/{teacher_id}/subjects", response_model=TeacherSubjectRead, status_code=status.HTTP_201_CREATED)
def assign_teacher_subject(
    teacher_id: int,
    payload: TeacherSubjectCreate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school_id = current_user.school_id
    _get_or_404(db, Teacher, teacher_id, school_id)
    _validate_same_school(db, Subject, payload.subject_id, school_id, "Subject")
    _validate_same_school(db, SchoolClass, payload.class_id, school_id, "Class")
    _validate_same_school(db, Section, payload.section_id, school_id, "Section")
    _validate_section_belongs_to_class(db, payload.section_id, payload.class_id, school_id)

    assignment = TeacherSubject(school_id=school_id, teacher_id=teacher_id, **payload.model_dump())
    db.add(assignment)
    _commit_or_duplicate(db, "This teacher-subject assignment already exists")
    db.refresh(assignment)
    return assignment

# Compatibility registration: app.main already includes people.router in every build.
# Including the separate profile router here guarantees /profile works even if
# an older main.py is still being used during patch application.
from app.routes import profile as profile_routes  # noqa: E402

router.include_router(profile_routes.router)

