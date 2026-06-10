from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_query import async_query
from app.core.database import get_async_db
from app.models.academic import AcademicSession
from app.models.user import User, UserRole
from app.dependencies.auth import get_current_user

ADMIN_ROLE_VALUES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
}

SESSION_HEADER = "X-Academic-Session-Id"


def _parse_session_id(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Academic session id must be a number",
        )


async def active_academic_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    active = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active.is_(True),
    ).order_by(AcademicSession.id.desc()).first()
    if active:
        return active

    return await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
    ).order_by(AcademicSession.id.desc()).first()


async def get_academic_session_or_404(
    db: AsyncSession,
    school_id: int,
    session_id: int,
) -> AcademicSession:
    session = await async_query(db, AcademicSession).filter(
        AcademicSession.id == session_id,
        AcademicSession.school_id == school_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Academic session not found")
    return session


async def selected_academic_session(
    db: AsyncSession,
    school_id: int,
    request: Request | None = None,
    current_user: User | None = None,
    explicit_session_id: int | str | None = None,
) -> AcademicSession | None:
    """Resolve the session for the current request.

    Admin users may select any session of their school. Teachers, students and
    parents are kept on the active session only, even if a stale client sends an
    old session id.
    """
    requested_id = _parse_session_id(explicit_session_id)
    if requested_id is None and request is not None:
        requested_id = _parse_session_id(
            request.headers.get(SESSION_HEADER)
            or request.query_params.get("academic_session_id")
            or request.query_params.get("session_id")
        )

    if requested_id is not None:
        session = await get_academic_session_or_404(db, school_id, requested_id)
        if current_user and current_user.role not in ADMIN_ROLE_VALUES and not session.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only school admins can access previous academic sessions",
            )
        return session

    return await active_academic_session(db, school_id)


async def selected_academic_session_id(
    db: AsyncSession,
    school_id: int,
    request: Request | None = None,
    current_user: User | None = None,
    explicit_session_id: int | str | None = None,
) -> int | None:
    session = await selected_academic_session(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
        explicit_session_id=explicit_session_id,
    )
    return session.id if session else None


def apply_academic_session_filter(query, model, session_id: int | None):
    if session_id is not None and hasattr(model, "academic_session_id"):
        return query.filter(model.academic_session_id == session_id)
    return query


SAFE_SESSION_METHODS = {"GET", "HEAD", "OPTIONS"}
READ_ONLY_SESSION_DETAIL = (
    "Selected academic session is read-only. Switch to the active academic session to create, update, or delete records."
)


def is_safe_session_method(request: Request) -> bool:
    return request.method.upper() in SAFE_SESSION_METHODS


async def assert_academic_session_is_writable(
    db: AsyncSession,
    school_id: int,
    academic_session_id: int | None,
) -> AcademicSession | None:
    """Raise 403 when a write targets a non-active academic session.

    This is a backend safety check. Frontend hiding buttons is useful, but the
    API must still protect historical academic records from direct requests.
    """
    if academic_session_id is None:
        return None
    session = await get_academic_session_or_404(db, school_id, academic_session_id)
    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=READ_ONLY_SESSION_DETAIL,
        )
    return session


async def writable_selected_academic_session(
    db: AsyncSession,
    school_id: int,
    request: Request | None = None,
    current_user: User | None = None,
    explicit_session_id: int | str | None = None,
) -> AcademicSession | None:
    """Resolve the selected session and require it to be active for writes."""
    session = await selected_academic_session(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
        explicit_session_id=explicit_session_id,
    )
    if session is not None and not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=READ_ONLY_SESSION_DETAIL,
        )
    return session


async def writable_selected_academic_session_id(
    db: AsyncSession,
    school_id: int,
    request: Request | None = None,
    current_user: User | None = None,
    explicit_session_id: int | str | None = None,
) -> int | None:
    session = await writable_selected_academic_session(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
        explicit_session_id=explicit_session_id,
    )
    return session.id if session else None


async def require_writable_academic_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Router dependency: non-GET requests cannot target previous sessions."""
    if is_safe_session_method(request):
        return
    if not current_user.school_id:
        return
    await writable_selected_academic_session(
        db=db,
        school_id=current_user.school_id,
        request=request,
        current_user=current_user,
    )


async def assert_item_session_is_writable(
    db: AsyncSession,
    school_id: int,
    item,
    session_attr: str = "academic_session_id",
) -> None:
    """Protect direct item-id writes even when the client omits the session header."""
    await assert_academic_session_is_writable(
        db=db,
        school_id=school_id,
        academic_session_id=getattr(item, session_attr, None),
    )
