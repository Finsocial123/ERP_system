from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Section
from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.people import ClassTeacherAssignment, Student, Teacher
from app.models.user import User, UserRole
from app.schemas.attendance import (
    AttendanceRead,
    AttendanceUpdate,
    BulkAttendanceCreate,
    DayAttendanceRecord,
    StudentAttendanceSummary,
)

router = APIRouter(prefix="/attendance", tags=["Phase 4 - Attendance"])

ADMIN_ROLES = [UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN]
ALLOWED_ROLES = [*ADMIN_ROLES, UserRole.TEACHER]

# The DB stores role as a plain string e.g. "TEACHER", not the enum object.
# Always compare against .value to be safe.
TEACHER_ROLE_VALUE = UserRole.TEACHER.value  # "TEACHER"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_session(db: Session, session_id: int, school_id: int) -> AcademicSession:
    sess = db.query(AcademicSession).filter(
        AcademicSession.id == session_id,
        AcademicSession.school_id == school_id,
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Academic session not found")
    return sess


def _validate_class(db: Session, class_id: int, school_id: int) -> SchoolClass:
    cls = db.query(SchoolClass).filter(
        SchoolClass.id == class_id,
        SchoolClass.school_id == school_id,
    ).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


def _student_full_name(s: Student) -> str:
    return f"{s.first_name} {s.last_name or ''}".strip()


def _is_teacher(user: User) -> bool:
    """Check if the user's role is TEACHER (compares string value, not enum)."""
    return user.role == TEACHER_ROLE_VALUE


def _get_teacher(db: Session, school_id: int, user: User) -> Teacher | None:
    """Resolve the Teacher record for the logged-in user."""
    return db.query(Teacher).filter(
        Teacher.user_id == user.id,
        Teacher.school_id == school_id,
    ).first()


def _teacher_allowed_class_ids(db: Session, school_id: int, teacher: Teacher) -> set[int]:
    """
    Return the set of class_ids a teacher is allowed to take attendance for.
    ONLY ClassTeacherAssignment is used — a teacher must be assigned as the
    class teacher of a class. Subject teacher assignment does NOT grant access.
    """
    return {
        row.class_id
        for row in db.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.teacher_id == teacher.id,
            ClassTeacherAssignment.school_id == school_id,
        ).all()
    }


def _assert_teacher_can_access_class(
    db: Session, school_id: int, user: User, class_id: int
) -> None:
    """
    Raise 403 if a TEACHER tries to access a class they are not assigned to.
    Admin roles pass through unconditionally.
    """
    if not _is_teacher(user):
        return  # admin/owner — no restriction

    teacher = _get_teacher(db, school_id, user)
    if not teacher:
        raise HTTPException(
            status_code=403,
            detail="No teacher profile found for your account. Contact admin.",
        )

    allowed = _teacher_allowed_class_ids(db, school_id, teacher)
    if class_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this class.",
        )


# ── GET /attendance/my-classes ────────────────────────────────────────────────
# Returns only the classes the current teacher is assigned to.
# Admins get all classes. Used by the frontend class dropdown.
@router.get("/my-classes", response_model=list[dict])
def teacher_allowed_classes(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    if _is_teacher(current_user):
        teacher = _get_teacher(db, school_id, current_user)
        if not teacher:
            return []
        allowed_ids = _teacher_allowed_class_ids(db, school_id, teacher)
        if not allowed_ids:
            return []
        classes = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.id.in_(allowed_ids),
                SchoolClass.school_id == school_id,
                SchoolClass.is_active.is_(True),
            )
            .order_by(SchoolClass.name)
            .all()
        )
    else:
        classes = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.school_id == school_id,
                SchoolClass.is_active.is_(True),
            )
            .order_by(SchoolClass.name)
            .all()
        )

    return [{"id": c.id, "name": c.name} for c in classes]


# ── POST /attendance/bulk ─────────────────────────────────────────────────────
@router.post("/bulk", response_model=list[AttendanceRead], status_code=status.HTTP_201_CREATED)
def bulk_mark_attendance(
    payload: BulkAttendanceCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_session(db, payload.session_id, school_id)
    _validate_class(db, payload.class_id, school_id)
    _assert_teacher_can_access_class(db, school_id, current_user, payload.class_id)

    if payload.section_id:
        sec = db.query(Section).filter(
            Section.id == payload.section_id, Section.school_id == school_id
        ).first()
        if not sec:
            raise HTTPException(status_code=404, detail="Section not found")

    student_ids = [e.student_id for e in payload.entries]
    students = db.query(Student).filter(
        Student.id.in_(student_ids), Student.school_id == school_id
    ).all()
    found_ids = {s.id for s in students}
    missing = set(student_ids) - found_ids
    if missing:
        raise HTTPException(status_code=400, detail=f"Students not found: {sorted(missing)}")

    results = []
    for entry in payload.entries:
        existing = db.query(StudentAttendance).filter(
            StudentAttendance.school_id == school_id,
            StudentAttendance.student_id == entry.student_id,
            StudentAttendance.date == payload.date,
            StudentAttendance.session_id == payload.session_id,
        ).first()

        if existing:
            existing.status = entry.status
            existing.note = entry.note
            existing.marked_by = current_user.id
            results.append(existing)
        else:
            record = StudentAttendance(
                school_id=school_id,
                session_id=payload.session_id,
                student_id=entry.student_id,
                class_id=payload.class_id,
                section_id=payload.section_id,
                date=payload.date,
                status=entry.status,
                note=entry.note,
                marked_by=current_user.id,
            )
            db.add(record)
            results.append(record)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


# ── GET /attendance/sheet ─────────────────────────────────────────────────────
@router.get("/sheet", response_model=list[DayAttendanceRecord])
def get_attendance_sheet(
    session_id: int = Query(...),
    class_id: int = Query(...),
    date: date = Query(...),
    section_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_session(db, session_id, school_id)
    _validate_class(db, class_id, school_id)
    _assert_teacher_can_access_class(db, school_id, current_user, class_id)

    q = db.query(Student).filter(
        Student.school_id == school_id,
        Student.class_id == class_id,
        Student.is_active.is_(True),
    )
    if section_id:
        q = q.filter(Student.section_id == section_id)
    students = q.order_by(Student.roll_number, Student.first_name).all()

    existing = {
        a.student_id: a
        for a in db.query(StudentAttendance).filter(
            StudentAttendance.school_id == school_id,
            StudentAttendance.class_id == class_id,
            StudentAttendance.date == date,
            StudentAttendance.session_id == session_id,
        ).all()
    }

    return [
        DayAttendanceRecord(
            student_id=s.id,
            student_name=_student_full_name(s),
            admission_no=s.admission_no,
            roll_number=s.roll_number,
            status=existing[s.id].status if s.id in existing else None,
            note=existing[s.id].note if s.id in existing else None,
            attendance_id=existing[s.id].id if s.id in existing else None,
        )
        for s in students
    ]


# ── PATCH /attendance/{attendance_id} ─────────────────────────────────────────
@router.patch("/{attendance_id}", response_model=AttendanceRead)
def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    record = db.query(StudentAttendance).filter(
        StudentAttendance.id == attendance_id,
        StudentAttendance.school_id == school_id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    _assert_teacher_can_access_class(db, school_id, current_user, record.class_id)

    record.status = payload.status
    record.note = payload.note
    record.marked_by = current_user.id
    db.commit()
    db.refresh(record)
    return record


# ── GET /attendance/summary ───────────────────────────────────────────────────
@router.get("/summary", response_model=list[StudentAttendanceSummary])
def attendance_summary(
    session_id: int = Query(...),
    class_id: int = Query(...),
    section_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_session(db, session_id, school_id)
    _validate_class(db, class_id, school_id)
    _assert_teacher_can_access_class(db, school_id, current_user, class_id)

    q = db.query(Student).filter(
        Student.school_id == school_id,
        Student.class_id == class_id,
        Student.is_active.is_(True),
    )
    if section_id:
        q = q.filter(Student.section_id == section_id)
    students = q.order_by(Student.first_name).all()

    summaries = []
    for s in students:
        records = db.query(StudentAttendance).filter(
            StudentAttendance.school_id == school_id,
            StudentAttendance.student_id == s.id,
            StudentAttendance.session_id == session_id,
        ).all()

        total    = len(records)
        present  = sum(1 for r in records if r.status == AttendanceStatus.PRESENT.value)
        absent   = sum(1 for r in records if r.status == AttendanceStatus.ABSENT.value)
        leave    = sum(1 for r in records if r.status == AttendanceStatus.LEAVE.value)
        half_day = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY.value)
        effective = present + (half_day * 0.5)
        percentage = round((effective / total * 100), 1) if total > 0 else 0.0

        summaries.append(StudentAttendanceSummary(
            student_id=s.id,
            student_name=_student_full_name(s),
            admission_no=s.admission_no,
            total_days=total,
            present=present,
            absent=absent,
            leave=leave,
            half_day=half_day,
            percentage=percentage,
            low_attendance=percentage < 75 and total > 0,
        ))
    return summaries


# ── GET /attendance/by-date ───────────────────────────────────────────────────
@router.get("/by-date", response_model=list[AttendanceRead])
def attendance_by_date(
    session_id: int = Query(...),
    class_id: int = Query(...),
    date: date = Query(...),
    section_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    _assert_teacher_can_access_class(db, school_id, current_user, class_id)

    q = db.query(StudentAttendance).filter(
        StudentAttendance.school_id == school_id,
        StudentAttendance.class_id == class_id,
        StudentAttendance.date == date,
        StudentAttendance.session_id == session_id,
    )
    if section_id:
        q = q.filter(StudentAttendance.section_id == section_id)
    return q.all()


# ── GET /attendance/my ────────────────────────────────────────────────────────
@router.get("/my", response_model=list[AttendanceRead])
def my_attendance(
    session_id: int = Query(...),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(
        Student.user_id == current_user.id,
        Student.school_id == school_id,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found for this user")

    return (
        db.query(StudentAttendance)
        .filter(
            StudentAttendance.school_id == school_id,
            StudentAttendance.student_id == student.id,
            StudentAttendance.session_id == session_id,
        )
        .order_by(StudentAttendance.date.desc())
        .all()
    )