"""Helpers for creating in-app notifications from ERP modules.

The notification API already exposes /communication/notifications.  These
helpers keep homework, exam, attendance, LMS and meeting routes from duplicating
recipient lookup logic while still writing to the same in_app_notifications table.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_query import async_query
from app.models.communication import InAppNotification
from app.models.people import ParentGuardian, Student, Teacher
from app.models.user import User, UserRole


def _clean_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _dedupe_user_ids(user_ids: Iterable[int | None]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for user_id in user_ids:
        if user_id is None:
            continue
        try:
            normalized = int(user_id)
        except (TypeError, ValueError):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def create_notification(
    db: AsyncSession,
    *,
    school_id: int,
    title: str,
    message: str,
    category: str = "GENERAL",
    created_by: int | None = None,
    priority: str = "NORMAL",
    target_role: str | None = None,
    target_user_id: int | None = None,
    link: str | None = "/notifications",
    expires_at: datetime | None = None,
) -> None:
    """Queue one notification in the current DB transaction."""
    db.add(
        InAppNotification(
            school_id=school_id,
            title=_clean_text(title, "Notification")[:255],
            message=_clean_text(message, title),
            category=(category or "GENERAL").upper(),
            priority=(priority or "NORMAL").upper(),
            target_role=target_role,
            target_user_id=target_user_id,
            link=link,
            expires_at=expires_at,
            created_by=created_by,
        )
    )


def notify_user_ids(
    db: AsyncSession,
    *,
    school_id: int,
    user_ids: Iterable[int | None],
    title: str,
    message: str,
    category: str = "GENERAL",
    created_by: int | None = None,
    priority: str = "NORMAL",
    link: str | None = "/notifications",
) -> int:
    """Queue a targeted notification for each user id and return count queued."""
    target_ids = _dedupe_user_ids(user_ids)
    for user_id in target_ids:
        create_notification(
            db,
            school_id=school_id,
            target_user_id=user_id,
            title=title,
            message=message,
            category=category,
            priority=priority,
            created_by=created_by,
            link=link,
        )
    return len(target_ids)


def notify_roles(
    db: AsyncSession,
    *,
    school_id: int,
    roles: Iterable[str | UserRole],
    title: str,
    message: str,
    category: str = "GENERAL",
    created_by: int | None = None,
    priority: str = "NORMAL",
    link: str | None = "/notifications",
) -> int:
    """Queue one role-wide notification per role."""
    normalized_roles: list[str] = []
    for role in roles:
        value = role.value if isinstance(role, UserRole) else str(role)
        if value and value not in normalized_roles:
            normalized_roles.append(value)
    for role in normalized_roles:
        create_notification(
            db,
            school_id=school_id,
            target_role=role,
            title=title,
            message=message,
            category=category,
            priority=priority,
            created_by=created_by,
            link=link,
        )
    return len(normalized_roles)


async def active_students_for_scope(
    db: AsyncSession,
    *,
    school_id: int,
    class_id: int | None,
    section_id: int | None = None,
    academic_session_id: int | None = None,
) -> list[Student]:
    """Students who should receive an update for a class/section/session item."""
    if class_id is None:
        return []
    query = async_query(db, Student).filter(
        Student.school_id == school_id,
        Student.class_id == class_id,
        Student.is_active.is_(True),
    )
    if section_id is not None:
        query = query.filter(Student.section_id == section_id)
    if academic_session_id is not None:
        query = query.filter(Student.academic_session_id == academic_session_id)
    return await query.all()


async def parent_user_ids_for_students(
    db: AsyncSession,
    *,
    school_id: int,
    students: Iterable[Student],
) -> list[int]:
    guardian_ids = {student.guardian_id for student in students if student.guardian_id is not None}
    if not guardian_ids:
        return []
    guardians = await async_query(db, ParentGuardian).filter(
        ParentGuardian.school_id == school_id,
        ParentGuardian.id.in_(guardian_ids),
        ParentGuardian.is_active.is_(True),
        ParentGuardian.user_id.isnot(None),
    ).all()
    return _dedupe_user_ids(guardian.user_id for guardian in guardians)


async def notify_student_scope(
    db: AsyncSession,
    *,
    school_id: int,
    class_id: int | None,
    section_id: int | None = None,
    academic_session_id: int | None = None,
    title: str,
    message: str,
    category: str,
    created_by: int | None = None,
    priority: str = "NORMAL",
    student_link: str | None = "/notifications",
    parent_link: str | None = "/notifications",
) -> int:
    """Notify all students and their linked parents for a class/section item."""
    students = await active_students_for_scope(
        db,
        school_id=school_id,
        class_id=class_id,
        section_id=section_id,
        academic_session_id=academic_session_id,
    )
    student_count = notify_user_ids(
        db,
        school_id=school_id,
        user_ids=[student.user_id for student in students],
        title=title,
        message=message,
        category=category,
        priority=priority,
        created_by=created_by,
        link=student_link,
    )
    parent_count = notify_user_ids(
        db,
        school_id=school_id,
        user_ids=await parent_user_ids_for_students(db, school_id=school_id, students=students),
        title=title,
        message=message,
        category=category,
        priority=priority,
        created_by=created_by,
        link=parent_link,
    )
    return student_count + parent_count


async def notify_student_record(
    db: AsyncSession,
    *,
    school_id: int,
    student: Student,
    title: str,
    message: str,
    category: str,
    created_by: int | None = None,
    priority: str = "NORMAL",
    student_link: str | None = "/notifications",
    parent_link: str | None = "/notifications",
) -> int:
    """Notify one student and their linked parent account."""
    count = notify_user_ids(
        db,
        school_id=school_id,
        user_ids=[student.user_id],
        title=title,
        message=message,
        category=category,
        priority=priority,
        created_by=created_by,
        link=student_link,
    )
    count += notify_user_ids(
        db,
        school_id=school_id,
        user_ids=await parent_user_ids_for_students(db, school_id=school_id, students=[student]),
        title=title,
        message=message,
        category=category,
        priority=priority,
        created_by=created_by,
        link=parent_link,
    )
    return count


async def notify_teacher_record(
    db: AsyncSession,
    *,
    school_id: int,
    teacher_id: int | None,
    title: str,
    message: str,
    category: str,
    created_by: int | None = None,
    priority: str = "NORMAL",
    link: str | None = "/notifications",
) -> int:
    if teacher_id is None:
        return 0
    teacher = await async_query(db, Teacher).filter(
        Teacher.school_id == school_id,
        Teacher.id == teacher_id,
        Teacher.is_active.is_(True),
    ).first()
    if not teacher:
        return 0
    return notify_user_ids(
        db,
        school_id=school_id,
        user_ids=[teacher.user_id],
        title=title,
        message=message,
        category=category,
        priority=priority,
        created_by=created_by,
        link=link,
    )


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d %b %Y")
