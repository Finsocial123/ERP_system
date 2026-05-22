from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Section
from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.people import Student
from app.models.user import User, UserRole
from app.schemas.attendance import (
    AttendanceRead,
    AttendanceUpdate,
    BulkAttendanceCreate,
    DayAttendanceRecord,
    StudentAttendanceSummary,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/attendance", tags=["Phase 4 - Attendance"])

ALLOWED_ROLES = [
    UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN, UserRole.TEACHER
]


def _validate_session(db: Session, session_id: int, school_id: int) -> AcademicSession:
    sess = db.query(AcademicSession).filter(
        AcademicSession.id == session_id, AcademicSession.school_id == school_id
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Academic session not found")
    return sess


def _validate_class(db: Session, class_id: int, school_id: int) -> SchoolClass:
    cls = db.query(SchoolClass).filter(
        SchoolClass.id == class_id, SchoolClass.school_id == school_id
    ).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


def _student_full_name(s: Student) -> str:
    return f"{s.first_name} {s.last_name or ''}".strip()


# ── Bulk mark attendance for a class on a date ──────────────────────────────
@router.post("/bulk", response_model=list[AttendanceRead], status_code=status.HTTP_201_CREATED)
def bulk_mark_attendance(
    payload: BulkAttendanceCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALLOWED_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_session(db, payload.session_id, school_id)
    _validate_class(db, payload.class_id, school_id)

    if payload.section_id:
        sec = db.query(Section).filter(
            Section.id == payload.section_id, Section.school_id == school_id
        ).first()
        if not sec:
            raise HTTPException(status_code=404, detail="Section not found")

    # Validate all student_ids belong to this school
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


# ── Get attendance sheet for a class on a date (with student list) ───────────
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

    records = []
    for s in students:
        att = existing.get(s.id)
        records.append(DayAttendanceRecord(
            student_id=s.id,
            student_name=_student_full_name(s),
            admission_no=s.admission_no,
            roll_number=s.roll_number,
            status=att.status if att else None,
            note=att.note if att else None,
            attendance_id=att.id if att else None,
        ))
    return records


# ── Update single attendance record ─────────────────────────────────────────
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
    record.status = payload.status
    record.note = payload.note
    record.marked_by = current_user.id
    db.commit()
    db.refresh(record)
    return record


# ── Student attendance summary (percentage + low attendance flag) ────────────
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

        total = len(records)
        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT.value)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT.value)
        leave = sum(1 for r in records if r.status == AttendanceStatus.LEAVE.value)
        half_day = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY.value)

        # present + half_day counts as 0.5 for percentage
        effective_present = present + (half_day * 0.5)
        percentage = round((effective_present / total * 100), 1) if total > 0 else 0.0

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


# ── Date-wise attendance list for a class ────────────────────────────────────
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
    q = db.query(StudentAttendance).filter(
        StudentAttendance.school_id == school_id,
        StudentAttendance.class_id == class_id,
        StudentAttendance.date == date,
        StudentAttendance.session_id == session_id,
    )
    if section_id:
        q = q.filter(StudentAttendance.section_id == section_id)
    return q.all()


# ── Student's own attendance (for student/parent role) ──────────────────────
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

    return db.query(StudentAttendance).filter(
        StudentAttendance.school_id == school_id,
        StudentAttendance.student_id == student.id,
        StudentAttendance.session_id == session_id,
    ).order_by(StudentAttendance.date.desc()).all()
