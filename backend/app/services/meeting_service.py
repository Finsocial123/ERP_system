import uuid
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload

from app.models.meeting import Meeting, MeetingType, MeetingStatus
from app.models.people import Teacher, TeacherSubject, Student
from app.models.user import User, UserRole
from app.services.bbb_service import create_bbb_meeting, get_join_url

def _generate_passwords():
    return secrets.token_urlsafe(12), secrets.token_urlsafe(12)


async def create_teacher_class_meeting(
    db: AsyncSession,
    school_id: int,
    teacher_id: int,
    class_id: int,
    section_id: int | None,
    title: str,
    created_by_user_id: int,
) -> Meeting:
    query = select(TeacherSubject).where(
        TeacherSubject.school_id == school_id,
        TeacherSubject.teacher_id == teacher_id,
        TeacherSubject.class_id == class_id,
    )
    if section_id:
        query = query.where(TeacherSubject.section_id == section_id)

    result = await db.execute(query)
    assignment = result.scalars().first()
    if not assignment:
        raise PermissionError("Teacher does not teach this class")

    meeting_id = f"school-{school_id}-class-{class_id}-{uuid.uuid4().hex[:8]}"
    attendee_pw, moderator_pw = _generate_passwords()

    await create_bbb_meeting(
        meeting_id=meeting_id,
        title=title,
        attendee_pw=attendee_pw,
        moderator_pw=moderator_pw,
    )

    meeting = Meeting(
        school_id=school_id,
        bbb_meeting_id=meeting_id,
        attendee_password=attendee_pw,
        moderator_password=moderator_pw,
        title=title,
        meeting_type=MeetingType.TEACHER_CLASS,
        status=MeetingStatus.LIVE,
        created_by_user_id=created_by_user_id,
        teacher_id=teacher_id,
        class_id=class_id,
        section_id=section_id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def create_admin_teachers_meeting(
    db: AsyncSession,
    school_id: int,
    title: str,
    created_by_user_id: int,
) -> Meeting:
    meeting_id = f"school-{school_id}-staff-{uuid.uuid4().hex[:8]}"
    attendee_pw, moderator_pw = _generate_passwords()

    await create_bbb_meeting(
        meeting_id=meeting_id,
        title=title,
        attendee_pw=attendee_pw,
        moderator_pw=moderator_pw,
    )

    meeting = Meeting(
        school_id=school_id,
        bbb_meeting_id=meeting_id,
        attendee_password=attendee_pw,
        moderator_password=moderator_pw,
        title=title,
        meeting_type=MeetingType.ADMIN_TEACHERS,
        status=MeetingStatus.LIVE,
        created_by_user_id=created_by_user_id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def get_meeting_join_url(
    db: AsyncSession,
    meeting_id: int,
    user_id: int,
    full_name: str,
    is_moderator: bool,
    user_role: str
) -> str:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting or meeting.status == MeetingStatus.ENDED:
        raise ValueError("Meeting not found or already ended")
    
    # Set logout URL based on role
    role_logout_urls = {
        "TEACHER": "http://localhost:3000/teachers/meetings",
        "STUDENT": "http://localhost:3000/students/meetings",
        "SCHOOL_ADMIN": "http://localhost:3000/setup/meetings",
        "SCHOOL_OWNER": "http://localhost:3000/setup/meetings",
        "SUPER_ADMIN": "http://localhost:3000/setup/meetings",
    }
    logout_url = role_logout_urls.get(user_role, "http://localhost:3000")


    password = meeting.moderator_password if is_moderator else meeting.attendee_password
    return get_join_url(
        meeting_id=meeting.bbb_meeting_id,
        full_name=full_name,
        password=password,
        user_id=str(user_id),
        logout_url=logout_url,
    )


async def end_meeting(
    db: AsyncSession,
    meeting_id: int,
    current_user: User,
) -> Meeting:
    from datetime import datetime
    from app.services.bbb_service import end_bbb_meeting

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")


    if meeting.created_by_user_id != current_user.id and current_user.role not in ("SCHOOL_ADMIN", "SUPER_ADMIN", "SCHOOL_OWNER"):
        raise PermissionError("Not allowed to end this meeting")

    await end_bbb_meeting(meeting.bbb_meeting_id, meeting.moderator_password)

    meeting.status = MeetingStatus.ENDED
    meeting.ended_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def get_active_meeting_for_class(
    db: AsyncSession,
    school_id: int,
    class_id: int,
    section_id: int | None = None,
) -> Meeting | None:
    query = select(Meeting).where(
        Meeting.school_id == school_id,
        Meeting.class_id == class_id,
        Meeting.section_id == section_id,
        Meeting.status == MeetingStatus.LIVE,
    )

    result = await db.execute(query)
    return result.scalars().first()


async def list_meetings(
    db: AsyncSession,
    current_user: User,
    skip: int = 0,
    limit: int = 20,
    status: MeetingStatus | None = None,
    meeting_type: MeetingType | None = None,
    search: str | None = None,
) -> dict:

    query = (
        select(Meeting)
        .options(joinedload(Meeting.created_by)) 
        .where(
            Meeting.school_id == current_user.school_id,
        )
    )

    if current_user.role == UserRole.STUDENT.value:
        student_result = await db.execute(
            select(Student)
            .where(
                Student.user_id == current_user.id,
                Student.school_id == current_user.school_id,
                Student.is_active.is_(True),
            )
            .order_by(Student.academic_session_id.desc().nullslast(), Student.id.desc())
            .limit(1)
        )
        student = student_result.scalars().first()
        if not student:
            return {"items": [], "total": 0}

        query = query.where(
            Meeting.class_id == student.class_id,
            Meeting.section_id == student.section_id,
            Meeting.meeting_type == MeetingType.TEACHER_CLASS, 
        )
        if student.section_id:
            query = query.where(
                Meeting.section_id == student.section_id,
            )

    elif current_user.role == UserRole.TEACHER.value:
        query = query.where(
            or_(
                Meeting.created_by_user_id == current_user.id,
                Meeting.meeting_type == MeetingType.ADMIN_TEACHERS,
            )
        )

    if status:
        query = query.where(Meeting.status == status)
    if meeting_type:
        query = query.where(Meeting.meeting_type == meeting_type)
    if search:
        query = query.where(Meeting.title.ilike(f"%{search}%"))

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    query = query.order_by(Meeting.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return {"items": items, "total": total}