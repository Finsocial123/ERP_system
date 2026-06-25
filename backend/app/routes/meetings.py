from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, case, func, or_
from sqlalchemy.orm import joinedload
from pydantic import BaseModel
from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.people import Teacher, TeacherSubject, Student
from app.models.meeting import Meeting, MeetingStatus, MeetingType
from app.services import meeting_service
from app.schemas.meetings import MeetingListOut, TeacherClassOut, TeacherMeetingCreate, AdminMeetingCreate, MeetingCreateOut, TeacherMeetingSchedule, AdminMeetingSchedule, MeetingListItemOut
from app.services.notification_service import notify_roles, notify_student_scope
router = APIRouter(prefix='/meetings', tags=['Meetings'])

@router.get('/stats')
async def meeting_stats(db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN))):
    result = await db.execute(select(func.count(Meeting.id).label('total'), func.sum(case((Meeting.status == MeetingStatus.LIVE, 1), else_=0)).label('live_now'), func.sum(case((Meeting.status == MeetingStatus.ENDED, 1), else_=0)).label('total_ended'), func.sum(case((Meeting.record == True, 1), else_=0)).label('recorded')).where(Meeting.school_id == current_user.school_id))
    row = result.one()
    return {'total_meetings': row.total or 0, 'live_now': row.live_now or 0, 'total_ended': row.total_ended or 0, 'recorded': row.recorded or 0}

@router.get('/active/class/{class_id}')
async def get_active_class_meeting(
    class_id: int, 
    db: AsyncSession=Depends(get_async_db), 
    current_user: User=Depends(get_current_user)
):
    meeting = await meeting_service.get_active_meeting_for_class(db=db, school_id=current_user.school_id, class_id=class_id)
    if not meeting:
        return {'live': False}
    return {'live': True, 'meeting_id': meeting.id, 'title': meeting.title}

@router.get('/', response_model=MeetingListOut)
async def list_meetings(skip: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100), status: MeetingStatus | None=Query(None), meeting_type: MeetingType | None=Query(None), search: str | None=Query(None), db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    return await meeting_service.list_meetings(db=db, current_user=current_user, skip=skip, limit=limit, status=status, meeting_type=meeting_type, search=search)

@router.post('/teacher/class', response_model=MeetingCreateOut, status_code=201)
async def teacher_create_class_meeting(
    payload: TeacherMeetingCreate, db: AsyncSession=Depends(get_async_db), 
    current_user: User=Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER))
):
    result = await db.execute(select(Teacher).where(Teacher.user_id == current_user.id, Teacher.school_id == current_user.school_id, Teacher.is_active == True))
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(403, 'No teacher profile found for this user')
    try:
        meeting = await meeting_service.create_teacher_class_meeting(db=db, school_id=current_user.school_id, teacher_id=teacher.id, class_id=payload.class_id, section_id=payload.section_id, section_name=payload.section_name, title=payload.title, created_by_user_id=current_user.id)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(503, f'BBB service error: {str(e)}')
    await notify_student_scope(
        db,
        school_id=current_user.school_id,
        class_id=meeting.class_id,
        section_id=meeting.section_id,
        academic_session_id=None,
        title='Class meeting is live',
        message=f"{meeting.title} has started.",
        category='MEETING',
        priority='HIGH',
        created_by=current_user.id,
        student_link='/students/meetings',
        parent_link='/students/meetings',
    )
    await db.commit()
    join_url = await meeting_service.get_meeting_join_url(db=db, meeting_id=meeting.id, user_id=current_user.id, full_name=teacher.full_name, is_moderator=True,     user_role=current_user.role)
    return {'meeting_id': meeting.id, 'join_url': join_url}

@router.post('/admin/teachers', response_model=MeetingCreateOut, status_code=201)
async def admin_create_teachers_meeting(
    payload: AdminMeetingCreate, 
    db: AsyncSession=Depends(get_async_db), 
    current_user: User=Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN))
):
    try:
        meeting = await meeting_service.create_admin_teachers_meeting(db=db, school_id=current_user.school_id, title=payload.title, created_by_user_id=current_user.id)
    except Exception as e:
        raise HTTPException(503, f'BBB service error: {str(e)}')
    notify_roles(
        db,
        school_id=current_user.school_id,
        roles=[UserRole.TEACHER],
        title='Staff meeting is live',
        message=f"{meeting.title} has started.",
        category='MEETING',
        priority='HIGH',
        created_by=current_user.id,
        link='/teachers/meetings',
    )
    await db.commit()
    join_url = await meeting_service.get_meeting_join_url(db=db, meeting_id=meeting.id, user_id=current_user.id, full_name=current_user.full_name, is_moderator=True, user_role=current_user.role)
    return {'meeting_id': meeting.id, 'join_url': join_url}




# all the classes teacher can create meeting for


@router.get("/teacher/my-classes")
async def get_my_classes(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER))
): 
    result = await db.execute(
        select(Teacher).where(
            Teacher.user_id == current_user.id,
            Teacher.school_id == current_user.school_id,
            Teacher.is_active == True,
        )
    )
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(403, "No teacher profile found")
    
    classes = await meeting_service.get_teacher_classes(
        db=db,
        school_id=current_user.school_id,
        teacher_id=teacher.id,
    )
    
    return {"classes": classes}


# get studentw in a class

@router.get("/class/{class_id}/students")
async def get_class_students(
    class_id: int,
    section_id: int | None = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER))
):
    students = await meeting_service.get_students_for_class(
        db=db,
        school_id=current_user.school_id,
        class_id=class_id,
        section_id=section_id,
    )

    return {
        "total": len(students),
        "students": [
            {
                "id": s.id,
                "name": f"{s.first_name} {s.last_name or ''}".strip(),
                "user_id": s.user_id,
            }
            for s in students
        ]
    }



# schedule meeting

@router.post("/teacher/class/schedule", response_model=MeetingListItemOut, status_code=201)
async def schedule_teacher_class_meeting(
    payload: TeacherMeetingSchedule,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER)),
):
    result = await db.execute(select(Teacher).where(
        Teacher.user_id == current_user.id,
        Teacher.school_id == current_user.school_id,
        Teacher.is_active == True,
    ))
    teacher = result.scalars().first()

    if not teacher:
        raise HTTPException(403, "No teacher profile found")
    try:
        meeting = await meeting_service.schedule_teacher_class_meeting(
            db=db, school_id=current_user.school_id, teacher_id=teacher.id,
            class_id=payload.class_id, section_id=payload.section_id, section_name=payload.section_name,
            title=payload.title, scheduled_at=payload.scheduled_at,
            created_by_user_id=current_user.id,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    await notify_student_scope(
        db,
        school_id=current_user.school_id,
        class_id=meeting.class_id,
        section_id=meeting.section_id,
        academic_session_id=None,
        title='Class meeting scheduled',
        message=f"{meeting.title} has been scheduled.",
        category='MEETING',
        priority='NORMAL',
        created_by=current_user.id,
        student_link='/students/meetings',
        parent_link='/students/meetings',
    )
    await db.commit()
    return meeting


@router.post("/admin/teachers/schedule", response_model=MeetingListItemOut, status_code=201)
async def schedule_admin_teachers_meeting(
    payload: AdminMeetingSchedule,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)),
):
    meeting = await meeting_service.schedule_admin_teachers_meeting(
        db=db, school_id=current_user.school_id, title=payload.title,
        scheduled_at=payload.scheduled_at, created_by_user_id=current_user.id,
    )
    notify_roles(
        db,
        school_id=current_user.school_id,
        roles=[UserRole.TEACHER],
        title='Staff meeting scheduled',
        message=f"{meeting.title} has been scheduled.",
        category='MEETING',
        priority='NORMAL',
        created_by=current_user.id,
        link='/teachers/meetings',
    )
    await db.commit()
    return meeting


@router.post("/{meeting_id}/start", response_model=MeetingCreateOut, status_code=200)
async def start_scheduled_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)),
):
    try:
        meeting = await meeting_service.start_scheduled_meeting(
            db=db, meeting_id=meeting_id, current_user=current_user
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(503, f"BBB service error: {str(e)}")

    if meeting.meeting_type == MeetingType.ADMIN_TEACHERS:
        notify_roles(
            db,
            school_id=current_user.school_id,
            roles=[UserRole.TEACHER],
            title='Staff meeting is live',
            message=f"{meeting.title} has started.",
            category='MEETING',
            priority='HIGH',
            created_by=current_user.id,
            link='/teachers/meetings',
        )
    else:
        await notify_student_scope(
            db,
            school_id=current_user.school_id,
            class_id=meeting.class_id,
            section_id=meeting.section_id,
            academic_session_id=None,
            title='Class meeting is live',
            message=f"{meeting.title} has started.",
            category='MEETING',
            priority='HIGH',
            created_by=current_user.id,
            student_link='/students/meetings',
            parent_link='/students/meetings',
        )
    await db.commit()

    full_name = current_user.full_name
    result = await db.execute(select(Teacher).where(
        Teacher.user_id == current_user.id,
        Teacher.school_id == current_user.school_id,
    ))
    teacher = result.scalar_one_or_none()
    if teacher:
        full_name = teacher.full_name

    join_url = await meeting_service.get_meeting_join_url(
        db=db, meeting_id=meeting.id, user_id=current_user.id,
        full_name=full_name, is_moderator=True, user_role=current_user.role,
    )
    return {"meeting_id": meeting.id, "join_url": join_url}


@router.delete("/{meeting_id}/cancel", status_code=200)
async def cancel_scheduled_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN)),
):
    try:
        meeting = await meeting_service.cancel_scheduled_meeting(
            db=db, meeting_id=meeting_id, current_user=current_user
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    if meeting.meeting_type == MeetingType.ADMIN_TEACHERS:
        notify_roles(
            db,
            school_id=current_user.school_id,
            roles=[UserRole.TEACHER],
            title='Staff meeting cancelled',
            message=f"{meeting.title} was cancelled.",
            category='MEETING',
            priority='NORMAL',
            created_by=current_user.id,
            link='/teachers/meetings',
        )
    else:
        await notify_student_scope(
            db,
            school_id=current_user.school_id,
            class_id=meeting.class_id,
            section_id=meeting.section_id,
            academic_session_id=None,
            title='Class meeting cancelled',
            message=f"{meeting.title} was cancelled.",
            category='MEETING',
            priority='NORMAL',
            created_by=current_user.id,
            student_link='/students/meetings',
            parent_link='/students/meetings',
        )
    await db.commit()
    return {"message": "Meeting cancelled"}









# create meeting


@router.get('/{meeting_id}/join')
async def join_meeting(meeting_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):

    meeting = await db.get(Meeting, meeting_id)

    if not meeting: 
        raise HTTPException(404, "Meeting not found")   
    
    if meeting.meeting_type == MeetingType.ADMIN_TEACHERS:
        is_moderator = current_user.role in (
            UserRole.SCHOOL_ADMIN,
            UserRole.SCHOOL_OWNER, 
            UserRole.SUPER_ADMIN, 
        )
    else:
        is_moderator = current_user.role in (
            UserRole.SCHOOL_ADMIN, 
            UserRole.SCHOOL_OWNER, 
            UserRole.SUPER_ADMIN, 
            UserRole.TEACHER
        )

    try:
        join_url = await meeting_service.get_meeting_join_url(
            db=db, 
            meeting_id=meeting_id, 
            user_id=current_user.id, 
            full_name=current_user.full_name, is_moderator=is_moderator, user_role=current_user.role
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {'join_url': join_url}

@router.post('/{meeting_id}/end', status_code=200)
async def end_meeting(meeting_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_roles(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SUPER_ADMIN))):
    try:
        meeting = await meeting_service.end_meeting(db, meeting_id, current_user)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    return {'message': 'Meeting ended', 'meeting_id': meeting.id}

