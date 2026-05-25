# app/routers/meetings.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.schemas.meetings import MeetingListOut

from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles
from sqlalchemy.orm import joinedload
from app.models.user import User, UserRole
from app.models.people import Teacher, TeacherSubject
from app.services import meeting_service
from sqlalchemy import select
from app.models.meeting import Meeting, MeetingStatus, MeetingType
from sqlalchemy import case, func

router = APIRouter(prefix="/meetings", tags=["Meetings"])


class TeacherMeetingCreate(BaseModel):
    class_id: int
    section_id: int | None = None
    title: str


class AdminMeetingCreate(BaseModel):
    title: str


class MeetingOut(BaseModel):
    meeting_id: int
    join_url: str

    class Config:
        from_attributes = True



@router.post("/teacher/class", response_model=MeetingOut, status_code=201)
async def teacher_create_class_meeting(
    payload: TeacherMeetingCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(
        require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER)
    ),
):

    result = await db.execute(
        select(Teacher).where(
            Teacher.user_id == current_user.id,
            Teacher.school_id == current_user.school_id,
            Teacher.is_active == True,
        )
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(403, "No teacher profile found for this user")

    try:
        meeting = await meeting_service.create_teacher_class_meeting(
            db=db,
            school_id=current_user.school_id,
            teacher_id=teacher.id,
            class_id=payload.class_id,
            section_id=payload.section_id,
            title=payload.title,
            created_by_user_id=current_user.id,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))

    join_url = await meeting_service.get_meeting_join_url(
        db=db,
        meeting_id=meeting.id,
        user_id=current_user.id,
        full_name=teacher.full_name,
        is_moderator=True,       # teacher is always moderator
    )
    return {"meeting_id": meeting.id, "join_url": join_url}


# app/routes/teachers.py
@router.get("/me/classes")
async def get_my_classes(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.TEACHER)),
):
    result = await db.execute(
        select(TeacherSubject).options(
            joinedload(TeacherSubject.subject),
            joinedload(TeacherSubject.school_class),
            joinedload(TeacherSubject.section),
        ).where(
            TeacherSubject.teacher.has(user_id=current_user.id),
            TeacherSubject.school_id == current_user.school_id,
        )
    ) 
    assignments = result.scalars().all()
    return [
        {
            "class_id": a.class_id,
            "class_name": a.school_class.name,
            "section_id": a.section_id,
            "section_name": a.section.name if a.section else None,
            "subject_name": a.subject.name,
        }
        for a in assignments
    ]


@router.post("/admin/teachers", response_model=MeetingOut, status_code=201)
async def admin_create_teachers_meeting(
    payload: AdminMeetingCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(
        require_roles(UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)
    ),
):
    meeting = await meeting_service.create_admin_teachers_meeting(
        db=db,
        school_id=current_user.school_id,
        title=payload.title,
        created_by_user_id=current_user.id,
    )
    join_url = await meeting_service.get_meeting_join_url(
        db=db,
        meeting_id=meeting.id,
        user_id=current_user.id,
        full_name=current_user.full_name,
        is_moderator=True,
    )
    return {"meeting_id": meeting.id, "join_url": join_url}

@router.get("/stats")
async def meeting_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(
        require_roles(UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)
    ),
):
    from sqlalchemy import func
    result = await db.execute(
        select(
            func.count(Meeting.id).label("total"),
            func.sum(case((Meeting.status == MeetingStatus.LIVE, 1), else_=0)).label("live_now"),
            func.sum(case((Meeting.status == MeetingStatus.ENDED, 1), else_=0)).label("total_ended"),
            func.sum(case((Meeting.record == True, 1), else_=0)).label("recorded"),
        ).where(Meeting.school_id == current_user.school_id)
    )
    row = result.one()
    return {
        "total_meetings": row.total or 0,
        "live_now": row.live_now or 0,
        "total_ended": row.total_ended or 0,
        "recorded": row.recorded or 0,
    }



@router.get("/{meeting_id}/join")
async def join_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    is_moderator = current_user.role in (
        UserRole.SCHOOL_ADMIN,
        UserRole.SCHOOL_OWNER,
        UserRole.SUPER_ADMIN,
        UserRole.TEACHER,
    )
    try:
        join_url = await meeting_service.get_meeting_join_url(
            db=db,
            meeting_id=meeting_id,
            user_id=current_user.id,
            full_name=current_user.full_name,
            is_moderator=is_moderator,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return {"join_url": join_url}



@router.post("/{meeting_id}/end", status_code=200)
async def end_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(
        require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)
    ),
):
    try:
        meeting = await meeting_service.end_meeting(db, meeting_id, current_user)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    return {"message": "Meeting ended", "meeting_id": meeting.id}


# ── Check if a class has an active live session (for student dashboard) ───────

@router.get("/active/class/{class_id}")
async def get_active_class_meeting(
    class_id: int,
    section_id: int | None = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    meeting = await meeting_service.get_active_meeting_for_class(
        db=db,
        school_id=current_user.school_id,
        class_id=class_id,
        section_id=section_id,
    )
    if not meeting:
        return {"live": False}
    return {"live": True, "meeting_id": meeting.id, "title": meeting.title}


@router.get("/", response_model=MeetingListOut)
async def list_meetings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: MeetingStatus | None = Query(None),
    meeting_type: MeetingType | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    return await meeting_service.list_meetings(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status,
        meeting_type=meeting_type,
    )


@router.get("/stats")
async def meeting_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(
        require_roles(UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)
    )
):
    result = await db.execute(
        select(
            func.count(Meeting.id).label("total"),
            func.sum(
                case((Meeting.status == MeetingStatus.LIVE, 1), else_=0)
            ).label("live_now"),
            func.sum(
                case((Meeting.status == MeetingStatus.ENDED, 1), else_=0)
            ).label("total_ended"),
            func.sum(
                case((Meeting.record == True, 1), else_=0)
            ).label("recorded"),

        ).where(Meeting.school_id == current_user.school_id)
    )
    row = result.one()
    return {
        "total_meetings": row.total or 0,
        "live_now": row.live_now or 0,
        "total_ended": row.total_ended or 0,
        "recorded": row.recorded or 0
    }


