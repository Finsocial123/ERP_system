"""Safe parent-to-child scoping helpers used by parent portals.

Do not match guardians by phone number. In school/demo data the same phone
number is often reused, which can expose every student's homework, timetable,
fees or exam records to one parent account.
"""
from __future__ import annotations
from sqlalchemy import func
from app.models.people import ParentGuardian, Student
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query

def parent_identifiers(user: User) -> set[str]:
    """Stable identifiers that are unique enough for parent login matching."""
    return {str(item).strip().lower() for item in (user.email, user.login_id) if item and str(item).strip()}

async def parent_guardians_for_user(db: AsyncSession, school_id: int, user: User) -> list[ParentGuardian]:
    """Return guardian rows that safely belong to the logged-in parent.

    Priority:
    1. Active guardian rows explicitly linked through guardian.user_id.
    2. Among linked rows, keep rows whose guardian email matches the login.
    3. Allow exactly one linked no-email guardian, used by fallback parent logins.
    4. If nothing is linked, fall back to exact guardian email/login match only.

    Phone matching is intentionally excluded because shared/demo numbers can
    make parent portals show unrelated students.
    """
    identifiers = parent_identifiers(user)
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

async def children_for_parent(db: AsyncSession, school_id: int, user: User) -> list[Student]:
    """Return only active children linked to the logged-in parent."""
    guardians = await parent_guardians_for_user(db, school_id, user)
    guardian_ids = [guardian.id for guardian in guardians]
    if not guardian_ids:
        return []
    return await async_query(db, Student).filter(Student.school_id == school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True)).order_by(Student.first_name.asc(), Student.id.asc()).all()
