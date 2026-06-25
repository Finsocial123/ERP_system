import uuid
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload, selectinload
import asyncio

from datetime import datetime, timezone, timedelta

from app.models.meeting import Meeting, MeetingType, MeetingStatus
from app.models.people import Teacher, TeacherSubject, Student, ClassTeacherAssignment
from app.models.academic import SchoolClass
from app.models.user import User, UserRole
from app.services.bbb_service import create_bbb_meeting, get_join_url, is_meeting_running, end_bbb_meeting
from app.core.sections import validate_class_section_name, virtual_section_id_for_name



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
    section_name: str | None = None,
) -> Meeting:
    
    subject_query =select(TeacherSubject).where(
        TeacherSubject.school_id == school_id,
        TeacherSubject.teacher_id == teacher_id,
        TeacherSubject.class_id == class_id,
    )

    resolved_section_name = await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id)
    if resolved_section_name:
        subject_query = subject_query.where(TeacherSubject.section_name == resolved_section_name)
    subject_result = await db.execute(subject_query)
    subject_assignment = subject_result.scalars().first()

    class_teacher_result = await db.execute(
        select(ClassTeacherAssignment).where(
            ClassTeacherAssignment.school_id == school_id,
            ClassTeacherAssignment.teacher_id == teacher_id,
            ClassTeacherAssignment.class_id == class_id,
            or_(ClassTeacherAssignment.section_name == resolved_section_name, ClassTeacherAssignment.section_name.is_(None)),
        )
    )   

    class_teacher_assignment = class_teacher_result.scalars().first()

    if not subject_assignment and not class_teacher_assignment:
        raise PermissionError("Teacher does not have access to this class")
    
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
        section_id=None,
        section_name=resolved_section_name,
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



async def get_meeting_join_url(    db: AsyncSession,
    meeting_id: int,
    user_id: int,
    full_name: str,
    is_moderator: bool,
    user_role: str) -> str:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting or meeting.status == MeetingStatus.ENDED:
        raise ValueError("Meeting not found or already ended")

    if meeting.status == MeetingStatus.SCHEDULED:
        raise ValueError("Meeting has not started yet")

    if meeting.status == MeetingStatus.LIVE:
        # only check BBB if meeting is older than 30 seconds
        age = datetime.now(timezone.utc) - meeting.created_at.replace(tzinfo=timezone.utc)
        if age > timedelta(seconds=30):
            running = await is_meeting_running(meeting.bbb_meeting_id)
            if not running:
                meeting.status = MeetingStatus.ENDED
                meeting.ended_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(meeting)

    if meeting.status == MeetingStatus.ENDED:
        raise ValueError("Meeting not found or already ended")

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
        is_moderator=is_moderator,
    )

async def end_meeting(
    db: AsyncSession,
    meeting_id: int,
    current_user: User,
) -> Meeting:

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")

    if meeting.meeting_type == MeetingType.ADMIN_TEACHERS and current_user.role == UserRole.TEACHER.value:
        raise PermissionError("Teachers cannot end staff meetings")

    if meeting.created_by_user_id != current_user.id and current_user.role not in (
        UserRole.SCHOOL_ADMIN.value, 
        UserRole.SUPER_ADMIN.value, 
        UserRole.SCHOOL_OWNER.value
    ):
        raise PermissionError("Not allowed to end this meeting")

    await end_bbb_meeting(meeting.bbb_meeting_id, meeting.moderator_password)

    meeting.status = MeetingStatus.ENDED
    meeting.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def get_active_meeting_for_class(
    db: AsyncSession,
    school_id: int,
    class_id: int,
) -> Meeting | None:
    query = select(Meeting).where(
        Meeting.school_id == school_id,
        Meeting.class_id == class_id,
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
            Meeting.meeting_type == MeetingType.TEACHER_CLASS,
            or_(Meeting.section_name.is_(None), Meeting.section_name == student.section_name),
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



async def get_teacher_classes(
    db: AsyncSession,
    school_id: int,
    teacher_id: int,
) -> list[dict]:
    
    subject_result = await db.execute(
        select(
            TeacherSubject.class_id,
            TeacherSubject.section_id,
            TeacherSubject.section_name,
            SchoolClass.name.label("class_name"),
        )
        .select_from(TeacherSubject)
        .join(SchoolClass, SchoolClass.id == TeacherSubject.class_id)
        .where(
            TeacherSubject.school_id == school_id,
            TeacherSubject.teacher_id == teacher_id,
            TeacherSubject.class_id.isnot(None),
        )
        .distinct()
    )
    subject_classes = subject_result.all()

    class_teacher_result = await db.execute(
        select(
            ClassTeacherAssignment.class_id,
            ClassTeacherAssignment.section_id,
            ClassTeacherAssignment.section_name,
            SchoolClass.name.label("class_name"),
        )
        .select_from(ClassTeacherAssignment)
        .join(SchoolClass, SchoolClass.id == ClassTeacherAssignment.class_id)
        .where(
            ClassTeacherAssignment.school_id == school_id,
            ClassTeacherAssignment.teacher_id == teacher_id,
        )
        .distinct()
    )

    class_teacher_classes = class_teacher_result.all()

    seen = set()
    classes = []
    
    for row in list(subject_classes) + list(class_teacher_classes):
        section_name = row.section_name
        section_id = await virtual_section_id_for_name(db, school_id, row.class_id, section_name) if section_name else None
        key = (row.class_id, section_name)
        if key not in seen:
            seen.add(key)
            classes.append({
                "class_id": row.class_id,
                "section_id": section_id,
                "class_name": row.class_name,
                "section_name": section_name,
            })

    return classes


async def get_students_for_class(
    db: AsyncSession,
    school_id: int,
    class_id: int,
    section_id: int | None = None,
    section_name: str | None = None,
) -> list[Student]:
    query = select(Student).where(
        Student.school_id == school_id,
        Student.class_id == class_id,
        Student.is_active == True,
        Student.status == "ACTIVE",
    )
    resolved_section_name = await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id)
    if resolved_section_name:
        query = query.where(Student.section_name == resolved_section_name)
    elif section_id:
        query = query.where(Student.section_id == section_id)

    result = await db.execute(query)
    return result.scalars().all()


async def schedule_teacher_class_meeting(
    db: AsyncSession,
    school_id: int,
    teacher_id: int,
    class_id: int,
    section_id: int | None,
    title: str,
    scheduled_at: datetime,
    created_by_user_id: int,
    section_name: str | None = None,
) -> Meeting:
    # same permission check as create_teacher_class_meeting
    subject_query = select(TeacherSubject).where(
        TeacherSubject.school_id == school_id,
        TeacherSubject.teacher_id == teacher_id,
        TeacherSubject.class_id == class_id,
    )
    resolved_section_name = await validate_class_section_name(db, school_id, class_id, section_name=section_name, section_id=section_id)
    if resolved_section_name:
        subject_query = subject_query.where(TeacherSubject.section_name == resolved_section_name)
    subject_result = await db.execute(subject_query)
    subject_assignment = subject_result.scalars().first()

    class_teacher_result = await db.execute(
        select(ClassTeacherAssignment).where(
            ClassTeacherAssignment.school_id == school_id,
            ClassTeacherAssignment.teacher_id == teacher_id,
            ClassTeacherAssignment.class_id == class_id,
            or_(ClassTeacherAssignment.section_name == resolved_section_name, ClassTeacherAssignment.section_name.is_(None)),
        )
    )
    class_teacher_assignment = class_teacher_result.scalars().first()

    if not subject_assignment and not class_teacher_assignment:
        raise PermissionError("Teacher does not have access to this class")

    meeting = Meeting(
        school_id=school_id,
        title=title,
        meeting_type=MeetingType.TEACHER_CLASS,
        status=MeetingStatus.SCHEDULED,
        scheduled_at=scheduled_at,
        created_by_user_id=created_by_user_id,
        teacher_id=teacher_id,
        class_id=class_id,
        section_id=None,
        section_name=resolved_section_name,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def schedule_admin_teachers_meeting(
    db: AsyncSession,
    school_id: int,
    title: str,
    scheduled_at: datetime,
    created_by_user_id: int,
) -> Meeting:
    meeting = Meeting(
        school_id=school_id,
        title=title,
        meeting_type=MeetingType.ADMIN_TEACHERS,
        status=MeetingStatus.SCHEDULED,
        scheduled_at=scheduled_at,
        created_by_user_id=created_by_user_id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def start_scheduled_meeting(
    db: AsyncSession,
    meeting_id: int,
    current_user: User,
) -> Meeting:

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")
    
    if meeting.status != MeetingStatus.SCHEDULED:
        raise ValueError("Meeting is not in scheduled state")
    
    if meeting.meeting_type == MeetingType.ADMIN_TEACHERS and current_user.role == UserRole.TEACHER.value:
        raise PermissionError("Teachers cannot start staff meetings")
    
    if meeting.created_by_user_id != current_user.id and current_user.role not in (
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SUPER_ADMIN.value, 
        UserRole.SCHOOL_OWNER.value
    ):
        raise PermissionError("Not allowed to start this meeting")

    meeting_id_str = f"school-{meeting.school_id}-class-{meeting.class_id}-{uuid.uuid4().hex[:8]}"
    attendee_pw, moderator_pw = _generate_passwords()

    await create_bbb_meeting(
        meeting_id=meeting_id_str,
        title=meeting.title,
        attendee_pw=attendee_pw,
        moderator_pw=moderator_pw,
    )

    meeting.bbb_meeting_id = meeting_id_str
    meeting.attendee_password = attendee_pw
    meeting.moderator_password = moderator_pw
    meeting.status = MeetingStatus.LIVE
    meeting.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(meeting)
    return meeting


async def cancel_scheduled_meeting(
    db: AsyncSession,
    meeting_id: int,
    current_user: User,
) -> Meeting:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise ValueError("Meeting not found")
    if meeting.status != MeetingStatus.SCHEDULED:
        raise ValueError("Only scheduled meetings can be cancelled")
    if meeting.created_by_user_id != current_user.id and current_user.role not in ("SCHOOL_ADMIN", "SUPER_ADMIN", "SCHOOL_OWNER"):
        raise PermissionError("Not allowed to cancel this meeting")

    await db.delete(meeting)
    await db.commit()
    return meeting