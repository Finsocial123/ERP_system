from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.async_query import async_query
from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.communication import (
    Announcement,
    CommunicationStatus,
    Complaint,
    ComplaintStatus,
    InAppNotification,
    InAppNotificationRead,
    SchoolEvent,
)
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.communication import (
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    CommunicationOverview,
    ComplaintCreate,
    ComplaintOut,
    ComplaintUpdate,
    EventCreate,
    EventOut,
    EventUpdate,
    NotificationCreate,
    NotificationOut,
    UserMini,
)

router = APIRouter(prefix='/communication', tags=['Communication'])
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}
ALL_PORTAL_ROLES = [UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value, UserRole.TEACHER.value, UserRole.STUDENT.value, UserRole.PARENT.value]


def _school_id(user: User) -> int:
    if not user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')
    return user.school_id


def _is_admin(user: User) -> bool:
    return user.role in ADMIN_ROLES


def _roles_to_csv(roles: list[UserRole] | None) -> str | None:
    if not roles:
        return None
    return ','.join(role.value for role in roles)


def _csv_to_roles(value: str | None) -> list[str]:
    return [item for item in (value or '').split(',') if item]


def _audience_allows(audience_csv: str | None, user: User) -> bool:
    roles = set(_csv_to_roles(audience_csv))
    return not roles or user.role in roles or _is_admin(user)


def _audience_filter(audience_column, user: User):
    """SQL filter for CSV audience_roles without loading all rows into Python."""
    if _is_admin(user):
        return true()
    role = user.role
    return or_(
        audience_column.is_(None),
        audience_column == '',
        audience_column == role,
        audience_column.like(f'{role},%'),
        audience_column.like(f'%,{role},%'),
        audience_column.like(f'%,{role}'),
    )


def _user_mini(user: User | None) -> UserMini | None:
    if not user:
        return None
    return UserMini(id=user.id, full_name=user.full_name, role=user.role)


def _announcement_out(item: Announcement) -> AnnouncementOut:
    return AnnouncementOut(
        id=item.id,
        title=item.title,
        message=item.message,
        priority=item.priority,
        status=item.status,
        audience_roles=_csv_to_roles(item.audience_roles),
        start_at=item.start_at,
        end_at=item.end_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        author=_user_mini(item.author),
    )


def _event_out(item: SchoolEvent) -> EventOut:
    return EventOut(
        id=item.id,
        title=item.title,
        description=item.description,
        event_date=item.event_date,
        end_date=item.end_date,
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        category=item.category,
        status=item.status,
        audience_roles=_csv_to_roles(item.audience_roles),
        created_at=item.created_at,
        updated_at=item.updated_at,
        author=_user_mini(item.author),
    )


def _complaint_out(item: Complaint, viewer: User) -> ComplaintOut:
    creator = None if item.is_anonymous and not _is_admin(viewer) else _user_mini(item.creator)
    return ComplaintOut(
        id=item.id,
        subject=item.subject,
        description=item.description,
        category=item.category,
        priority=item.priority,
        status=item.status,
        action_taken=item.action_taken,
        is_anonymous=item.is_anonymous,
        created_at=item.created_at,
        updated_at=item.updated_at,
        resolved_at=item.resolved_at,
        creator=creator,
        assignee=_user_mini(item.assignee),
    )


def _notification_out(item: InAppNotification, read_ids: set[int]) -> NotificationOut:
    return NotificationOut.model_validate(item, from_attributes=True).model_copy(update={'is_read': item.id in read_ids, 'author': _user_mini(item.author)})


def _visible_notification_filters(user: User):
    now = datetime.utcnow()
    return (
        InAppNotification.school_id == _school_id(user),
        or_(InAppNotification.expires_at.is_(None), InAppNotification.expires_at > now),
        or_(InAppNotification.target_user_id.is_(None), InAppNotification.target_user_id == user.id),
        or_(InAppNotification.target_role.is_(None), InAppNotification.target_role == user.role),
    )


def _visible_notification_query(db: AsyncSession, user: User):
    return async_query(db, InAppNotification).options(selectinload(InAppNotification.author)).filter(*_visible_notification_filters(user))


async def _unread_notifications_count(db: AsyncSession, user: User) -> int:
    read_join = and_(
        InAppNotificationRead.notification_id == InAppNotification.id,
        InAppNotificationRead.user_id == user.id,
    )
    result = await db.execute(
        select(func.count(InAppNotification.id))
        .outerjoin(InAppNotificationRead, read_join)
        .where(*_visible_notification_filters(user), InAppNotificationRead.id.is_(None))
    )
    return int(result.scalar() or 0)


async def _load_announcement_for_response(db: AsyncSession, item_id: int) -> Announcement:
    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.author))
        .where(Announcement.id == item_id)
    )
    item = result.scalar_one()
    return item


async def _load_event_for_response(db: AsyncSession, item_id: int) -> SchoolEvent:
    result = await db.execute(
        select(SchoolEvent)
        .options(selectinload(SchoolEvent.author))
        .where(SchoolEvent.id == item_id)
    )
    item = result.scalar_one()
    return item


async def _load_complaint_for_response(db: AsyncSession, item_id: int) -> Complaint:
    result = await db.execute(
        select(Complaint)
        .options(selectinload(Complaint.creator), selectinload(Complaint.assignee))
        .where(Complaint.id == item_id)
    )
    item = result.scalar_one()
    return item


async def _load_notification_for_response(db: AsyncSession, item_id: int) -> InAppNotification:
    result = await db.execute(
        select(InAppNotification)
        .options(selectinload(InAppNotification.author))
        .where(InAppNotification.id == item_id)
    )
    item = result.scalar_one()
    return item


def _create_notification(
    db: AsyncSession,
    *,
    school_id: int,
    title: str,
    message: str,
    category: str,
    created_by: int | None,
    priority: str = 'NORMAL',
    target_role: str | None = None,
    target_user_id: int | None = None,
    link: str | None = None,
) -> None:
    db.add(InAppNotification(school_id=school_id, title=title, message=message, category=category, priority=priority, target_role=target_role, target_user_id=target_user_id, link=link, created_by=created_by))


def _broadcast_notification(db: AsyncSession, *, school_id: int, title: str, message: str, category: str, audience_csv: str | None, created_by: int | None, priority: str = 'NORMAL', link: str | None = None) -> None:
    roles = _csv_to_roles(audience_csv)
    if not roles:
        _create_notification(db, school_id=school_id, title=title, message=message, category=category, priority=priority, created_by=created_by, link=link)
        return
    for role in roles:
        _create_notification(db, school_id=school_id, title=title, message=message, category=category, priority=priority, target_role=role, created_by=created_by, link=link)


def _notify_admins(db: AsyncSession, school_id: int, title: str, message: str, category: str, created_by: int | None) -> None:
    for role in [UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value]:
        _create_notification(db, school_id=school_id, title=title, message=message, category=category, priority='HIGH', target_role=role, created_by=created_by, link='/communication')


@router.post('/announcements', response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
async def create_announcement(payload: AnnouncementCreate, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    school_id = _school_id(current_user)
    audience_csv = _roles_to_csv(payload.audience_roles)
    item = Announcement(
        school_id=school_id,
        created_by=current_user.id,
        title=payload.title,
        message=payload.message,
        priority=payload.priority.value,
        status=payload.status.value,
        audience_roles=audience_csv,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )
    db.add(item)
    await db.flush()
    if item.status == CommunicationStatus.PUBLISHED.value:
        _broadcast_notification(db, school_id=school_id, title=item.title, message=item.message[:250], category='ANNOUNCEMENT', priority=item.priority, audience_csv=audience_csv, created_by=current_user.id, link='/communication')
    await db.commit()
    return _announcement_out(await _load_announcement_for_response(db, item.id))


@router.get('/announcements', response_model=list[AnnouncementOut])
async def list_announcements(status_filter: CommunicationStatus | None=Query(default=None, alias='status'), skip: int=Query(default=0, ge=0), limit: int=Query(default=50, ge=1, le=200), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    q = async_query(db, Announcement).options(selectinload(Announcement.author)).filter(Announcement.school_id == _school_id(current_user))
    if status_filter:
        q = q.filter(Announcement.status == status_filter.value)
    elif not _is_admin(current_user):
        q = q.filter(Announcement.status == CommunicationStatus.PUBLISHED.value)
    q = q.filter(_audience_filter(Announcement.audience_roles, current_user))
    items = await q.order_by(Announcement.created_at.desc()).offset(skip).limit(limit).all()
    return [_announcement_out(item) for item in items]


@router.patch('/announcements/{announcement_id}', response_model=AnnouncementOut)
async def update_announcement(announcement_id: int, payload: AnnouncementUpdate, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    item = await async_query(db, Announcement).filter(Announcement.id == announcement_id, Announcement.school_id == _school_id(current_user)).first()
    if not item:
        raise HTTPException(status_code=404, detail='Announcement not found')
    data = payload.model_dump(exclude_unset=True)
    if 'audience_roles' in data:
        item.audience_roles = _roles_to_csv(payload.audience_roles)
        data.pop('audience_roles')
    for key, value in data.items():
        setattr(item, key, value.value if hasattr(value, 'value') else value)
    await db.commit()
    return _announcement_out(await _load_announcement_for_response(db, item.id))


@router.delete('/announcements/{announcement_id}', response_model=MessageResponse)
async def delete_announcement(announcement_id: int, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    item = await async_query(db, Announcement).filter(Announcement.id == announcement_id, Announcement.school_id == _school_id(current_user)).first()
    if not item:
        raise HTTPException(status_code=404, detail='Announcement not found')
    await db.delete(item)
    await db.commit()
    return MessageResponse(message='Announcement deleted successfully')


@router.post('/events', response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    school_id = _school_id(current_user)
    audience_csv = _roles_to_csv(payload.audience_roles)
    item = SchoolEvent(
        school_id=school_id,
        created_by=current_user.id,
        title=payload.title,
        description=payload.description,
        event_date=payload.event_date,
        end_date=payload.end_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        location=payload.location,
        category=payload.category,
        status=payload.status.value,
        audience_roles=audience_csv,
    )
    db.add(item)
    await db.flush()
    if item.status == CommunicationStatus.PUBLISHED.value:
        _broadcast_notification(db, school_id=school_id, title=f'Event: {item.title}', message=(item.description or item.title)[:250], category='MEETING' if (item.category or '').upper() == 'MEETING' else 'EVENT', priority='NORMAL', audience_csv=audience_csv, created_by=current_user.id, link='/communication')
    await db.commit()
    return _event_out(await _load_event_for_response(db, item.id))


@router.get('/events', response_model=list[EventOut])
async def list_events(from_date: date | None=Query(default=None), status_filter: CommunicationStatus | None=Query(default=None, alias='status'), skip: int=Query(default=0, ge=0), limit: int=Query(default=50, ge=1, le=200), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    q = async_query(db, SchoolEvent).options(selectinload(SchoolEvent.author)).filter(SchoolEvent.school_id == _school_id(current_user))
    if from_date:
        q = q.filter(SchoolEvent.event_date >= from_date)
    if status_filter:
        q = q.filter(SchoolEvent.status == status_filter.value)
    elif not _is_admin(current_user):
        q = q.filter(SchoolEvent.status == CommunicationStatus.PUBLISHED.value)
    q = q.filter(_audience_filter(SchoolEvent.audience_roles, current_user))
    items = await q.order_by(SchoolEvent.event_date.asc(), SchoolEvent.start_time.asc()).offset(skip).limit(limit).all()
    return [_event_out(item) for item in items]


@router.patch('/events/{event_id}', response_model=EventOut)
async def update_event(event_id: int, payload: EventUpdate, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    item = await async_query(db, SchoolEvent).filter(SchoolEvent.id == event_id, SchoolEvent.school_id == _school_id(current_user)).first()
    if not item:
        raise HTTPException(status_code=404, detail='Event not found')
    data = payload.model_dump(exclude_unset=True)
    if 'audience_roles' in data:
        item.audience_roles = _roles_to_csv(payload.audience_roles)
        data.pop('audience_roles')
    for key, value in data.items():
        setattr(item, key, value.value if hasattr(value, 'value') else value)
    await db.commit()
    return _event_out(await _load_event_for_response(db, item.id))


@router.delete('/events/{event_id}', response_model=MessageResponse)
async def delete_event(event_id: int, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    item = await async_query(db, SchoolEvent).filter(SchoolEvent.id == event_id, SchoolEvent.school_id == _school_id(current_user)).first()
    if not item:
        raise HTTPException(status_code=404, detail='Event not found')
    await db.delete(item)
    await db.commit()
    return MessageResponse(message='Event deleted successfully')


@router.post('/complaints', response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
async def create_complaint(payload: ComplaintCreate, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    school_id = _school_id(current_user)
    item = Complaint(school_id=school_id, created_by=current_user.id, subject=payload.subject, description=payload.description, category=payload.category, priority=payload.priority.value, status=ComplaintStatus.SUBMITTED.value, is_anonymous=payload.is_anonymous)
    db.add(item)
    await db.flush()
    _notify_admins(db, school_id, 'New complaint submitted', item.subject, 'COMPLAINT', None if payload.is_anonymous else current_user.id)
    await db.commit()
    return _complaint_out(await _load_complaint_for_response(db, item.id), current_user)


@router.get('/complaints', response_model=list[ComplaintOut])
async def list_complaints(status_filter: ComplaintStatus | None=Query(default=None, alias='status'), skip: int=Query(default=0, ge=0), limit: int=Query(default=50, ge=1, le=200), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    q = async_query(db, Complaint).options(selectinload(Complaint.creator), selectinload(Complaint.assignee)).filter(Complaint.school_id == _school_id(current_user))
    if not _is_admin(current_user):
        q = q.filter(Complaint.created_by == current_user.id)
    if status_filter:
        q = q.filter(Complaint.status == status_filter.value)
    items = await q.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()
    return [_complaint_out(item, current_user) for item in items]


@router.patch('/complaints/{complaint_id}', response_model=ComplaintOut)
async def update_complaint(complaint_id: int, payload: ComplaintUpdate, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    item = await async_query(db, Complaint).options(selectinload(Complaint.creator), selectinload(Complaint.assignee)).filter(Complaint.id == complaint_id, Complaint.school_id == _school_id(current_user)).first()
    if not item:
        raise HTTPException(status_code=404, detail='Complaint not found')
    if not _is_admin(current_user) and item.created_by != current_user.id:
        raise HTTPException(status_code=403, detail='You can update only your own complaints')
    data = payload.model_dump(exclude_unset=True)
    admin_only = {'status', 'assigned_to', 'action_taken'}
    if not _is_admin(current_user):
        data = {k: v for k, v in data.items() if k not in admin_only}
        if item.status not in {ComplaintStatus.SUBMITTED.value, ComplaintStatus.UNDER_REVIEW.value}:
            raise HTTPException(status_code=400, detail='Closed/resolved complaints cannot be edited by requester')
    old_status = item.status
    for key, value in data.items():
        setattr(item, key, value.value if hasattr(value, 'value') else value)
    if item.status in {ComplaintStatus.RESOLVED.value, ComplaintStatus.REJECTED.value, ComplaintStatus.CLOSED.value} and old_status != item.status:
        item.resolved_at = datetime.utcnow()
        if item.created_by:
            _create_notification(db, school_id=item.school_id, title='Complaint status updated', message=f"Your complaint '{item.subject}' is now {item.status.replace('_', ' ').title()}.", category='COMPLAINT', priority='NORMAL', target_user_id=item.created_by, created_by=current_user.id, link='/communication')
    await db.commit()
    return _complaint_out(await _load_complaint_for_response(db, item.id), current_user)


@router.post('/notifications', response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
async def create_notification(payload: NotificationCreate, current_user: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    item = InAppNotification(school_id=_school_id(current_user), created_by=current_user.id, title=payload.title, message=payload.message, category=payload.category, priority=payload.priority.value, target_role=payload.target_role.value if payload.target_role else None, target_user_id=payload.target_user_id, link=payload.link, expires_at=payload.expires_at)
    db.add(item)
    await db.commit()
    return _notification_out(await _load_notification_for_response(db, item.id), set())



@router.get('/notifications/unread-count')
async def unread_notifications_count(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    return {'count': await _unread_notifications_count(db, current_user)}


@router.get('/notifications', response_model=list[NotificationOut])
async def list_notifications(unread_only: bool=Query(default=False), skip: int=Query(default=0, ge=0), limit: int=Query(default=30, ge=1, le=100), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    query = _visible_notification_query(db, current_user).order_by(InAppNotification.created_at.desc())
    items = await query.all()
    ids = [item.id for item in items]
    read_ids: set[int] = set()
    if ids:
        read_ids = {row[0] for row in await async_query(db, InAppNotificationRead.notification_id).filter(InAppNotificationRead.user_id == current_user.id, InAppNotificationRead.notification_id.in_(ids)).all()}
    if unread_only:
        items = [item for item in items if item.id not in read_ids]
    return [_notification_out(item, read_ids) for item in items[skip:skip + limit]]


@router.post('/notifications/{notification_id}/read', response_model=MessageResponse)
async def mark_notification_read(notification_id: int, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    item = await _visible_notification_query(db, current_user).filter(InAppNotification.id == notification_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Notification not found')
    exists = await async_query(db, InAppNotificationRead).filter(InAppNotificationRead.notification_id == notification_id, InAppNotificationRead.user_id == current_user.id).first()
    if not exists:
        db.add(InAppNotificationRead(notification_id=notification_id, user_id=current_user.id))
        await db.commit()
    return MessageResponse(message='Notification marked as read')


@router.post('/notifications/read-all', response_model=MessageResponse)
async def mark_all_notifications_read(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    items = await _visible_notification_query(db, current_user).all()
    ids = [item.id for item in items]
    if not ids:
        return MessageResponse(message='No notifications to mark')
    existing = {row[0] for row in await async_query(db, InAppNotificationRead.notification_id).filter(InAppNotificationRead.user_id == current_user.id, InAppNotificationRead.notification_id.in_(ids)).all()}
    for notification_id in ids:
        if notification_id not in existing:
            db.add(InAppNotificationRead(notification_id=notification_id, user_id=current_user.id))
    await db.commit()
    return MessageResponse(message='All notifications marked as read')


@router.get('/overview', response_model=CommunicationOverview)
async def communication_overview(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    school_id = _school_id(current_user)
    today = date.today()
    announcement_query = async_query(db, func.count(Announcement.id)).filter(Announcement.school_id == school_id)
    event_query = async_query(db, func.count(SchoolEvent.id)).filter(SchoolEvent.school_id == school_id, SchoolEvent.event_date >= today)
    if _is_admin(current_user):
        announcements = await announcement_query.scalar() or 0
        upcoming_events = await event_query.scalar() or 0
        open_complaints = await async_query(db, func.count(Complaint.id)).filter(Complaint.school_id == school_id, Complaint.status.in_([ComplaintStatus.SUBMITTED.value, ComplaintStatus.UNDER_REVIEW.value])).scalar() or 0
    else:
        announcements = await announcement_query.filter(Announcement.status == CommunicationStatus.PUBLISHED.value, _audience_filter(Announcement.audience_roles, current_user)).scalar() or 0
        upcoming_events = await event_query.filter(SchoolEvent.status == CommunicationStatus.PUBLISHED.value, _audience_filter(SchoolEvent.audience_roles, current_user)).scalar() or 0
        open_complaints = await async_query(db, func.count(Complaint.id)).filter(Complaint.school_id == school_id, Complaint.created_by == current_user.id, Complaint.status.in_([ComplaintStatus.SUBMITTED.value, ComplaintStatus.UNDER_REVIEW.value])).scalar() or 0
    unread_notifications = await _unread_notifications_count(db, current_user)
    return CommunicationOverview(announcements=announcements, upcoming_events=upcoming_events, open_complaints=open_complaints, unread_notifications=unread_notifications)
