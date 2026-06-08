from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.client import client
from app.core.config import settings, MODEL
from app.models.notice import Notice, NoticeAudience, NoticeRead, NoticeStatus
from app.models.user import User, UserRole
from app.schemas.notice import NoticeCreate, NoticeListOut, NoticeOut, NoticeUpdate, NoticePriority
from sqlalchemy.dialects.postgresql import insert
from app.models.notice import Notice, NoticeAudience, NoticeClassAudience, NoticeRead, NoticeStatus
from app.models.people import Teacher, TeacherSubject, ClassTeacherAssignment 
from app.models.people import Student
from app.models.school import School
from sqlalchemy import or_


# Roles allowed to create/manage notices
NOTICE_MANAGER_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.SCHOOL_OWNER,
    UserRole.SCHOOL_ADMIN,
    UserRole.TEACHER,
}

ADMIN_VIEWER_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
}


def _can_manage(user: User) -> bool:
    return user.role in {r.value for r in NOTICE_MANAGER_ROLES}


def _load_options():
    return [
        selectinload(Notice.author),
        selectinload(Notice.audiences),
        selectinload(Notice.class_audiences),
    ]


# async def create_notice(
#     db: AsyncSession, payload: NoticeCreate, current_user: User
# ) -> Notice:
#     if not _can_manage(current_user):
#         raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

#     content = payload.content
#     if getattr(payload, "enhance", False):
#         content = await enhance_notice_content(content, current_user)

#     notice = Notice(
#         school_id=current_user.school_id,
#         created_by=current_user.id,
#         title=payload.title,
#         content=content,
#         priority=payload.priority.value,
#         status=payload.status.value,
#         publish_at=payload.publish_at,
#         expires_at=payload.expires_at,
#     )
#     db.add(notice)
#     await db.flush() 

#     for role in payload.audience_roles:
#         db.add(NoticeAudience(notice_id=notice.id, role=role.value))

#     await db.commit()
#     result = await db.execute(
#         select(Notice).options(*_load_options()).where(Notice.id == notice.id)
#     )
#     return result.scalar_one()


async def create_notice(
    db: AsyncSession, payload: NoticeCreate, current_user: User
) -> Notice:
    if not _can_manage(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    if payload.audience_class_ids and current_user.role == UserRole.TEACHER.value:
        allowed_pairs = await _get_teacher_allowed_pairs(
            db, current_user.id, current_user.school_id
        )
        if not allowed_pairs:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No teacher profile found")

        section_ids = payload.audience_section_ids or []
        submitted = {
            (class_id, section_ids[i] if i < len(section_ids) else None)
            for i, class_id in enumerate(payload.audience_class_ids)
        }

        forbidden = submitted - allowed_pairs
        if forbidden:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You can only target classes/sections you are assigned to",
            )

    content = payload.content
    if getattr(payload, "enhance", False):
        content = await enhance_notice_content(content, current_user)

    notice = Notice(
        school_id=current_user.school_id,
        created_by=current_user.id,
        title=payload.title,
        content=content,
        priority=payload.priority.value,
        status=payload.status.value,
        publish_at=payload.publish_at,
        expires_at=payload.expires_at,
    )
    db.add(notice)
    await db.flush()

    for role in payload.audience_roles:
        db.add(NoticeAudience(notice_id=notice.id, role=role.value))

    section_ids = payload.audience_section_ids or []
    for i, class_id in enumerate(payload.audience_class_ids):
        section_id = section_ids[i] if i < len(section_ids) else None
        db.add(NoticeClassAudience(
            notice_id=notice.id,
            class_id=class_id,
            section_id=section_id,
        ))

    await db.commit()
    result = await db.execute(
        select(Notice).options(*_load_options()).where(Notice.id == notice.id)
    )
    return result.scalar_one()

async def get_notice(
    db: AsyncSession, notice_id: int, current_user: User
) -> NoticeOut:
    result = await db.execute(
        select(Notice)
        .options(*_load_options())
        .where(
            Notice.id == notice_id,
            Notice.school_id == current_user.school_id,
        )
    )
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notice not found")
    

    if notice.class_audiences and notice.created_by != current_user.id and current_user.role not in {
    UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value
    }:
        if current_user.role == UserRole.STUDENT.value:
            student_result = await db.execute(
                select(Student.class_id, Student.section_id).where(
                    Student.user_id == current_user.id,
                    Student.school_id == current_user.school_id,
                )
            )
            student = student_result.first()
            if not student:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not in this notice's audience")
            allowed_pairs = {(a.class_id, a.section_id) for a in notice.class_audiences}
            if (student.class_id, student.section_id) not in allowed_pairs and \
               (student.class_id, None) not in allowed_pairs:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not in this notice's audience")

    _check_audience(notice, current_user)

    read_result = await db.execute(
        select(NoticeRead).where(
            NoticeRead.notice_id == notice_id,
            NoticeRead.user_id == current_user.id,
        )
    )
    is_read = read_result.scalar_one_or_none() is not None

    count_result = await db.execute(
        select(func.count()).where(NoticeRead.notice_id == notice_id)
    )
    read_count = count_result.scalar_one()

    out = NoticeOut.model_validate(notice)
    out.is_read = is_read
    out.read_count = read_count
    return out



async def list_notices(
    db: AsyncSession,
    current_user: User,
    skip: int = 0,
    limit: int = 20,
    status_filter: NoticeStatus | None = None,
    priority_filter: NoticePriority | None = None,
    pinned_only: bool = False,
    exclude_self: bool = False,
    created_by_self: bool = False,
    unread_only: bool = False
) -> NoticeListOut:
    now = datetime.now(timezone.utc)

    base_query = (
        select(Notice)
        .options(*_load_options())
        .where(Notice.school_id == current_user.school_id)
    )

    if not created_by_self and current_user.role not in ADMIN_VIEWER_ROLES:
        base_query = base_query.where(
            ~Notice.audiences.any()
            | Notice.audiences.any(NoticeAudience.role == current_user.role)
        )

    if not created_by_self and current_user.role not in ADMIN_VIEWER_ROLES:
        if current_user.role == UserRole.STUDENT.value:
            student_result = await db.execute(
                select(Student.class_id, Student.section_id).where(
                    Student.user_id == current_user.id,
                    Student.school_id == current_user.school_id,
                    Student.is_active.is_(True),
                )
            )
            student = student_result.first()
            if student and student.class_id:
                base_query = base_query.where(
                    ~Notice.class_audiences.any()
                    | Notice.class_audiences.any(
                        (NoticeClassAudience.class_id == student.class_id)
                        & (
                            NoticeClassAudience.section_id.is_(None)
                            | (NoticeClassAudience.section_id == student.section_id)
                        )
                    )
                )
            else:
                base_query = base_query.where(~Notice.class_audiences.any())

        elif current_user.role == UserRole.TEACHER.value:
            teacher_result = await db.execute(
                select(Teacher).where(
                    Teacher.user_id == current_user.id,
                    Teacher.school_id == current_user.school_id,
                    Teacher.is_active.is_(True),
                )
            )
            teacher = teacher_result.scalar_one_or_none()
            if teacher:
                subject_classes = select(
                    TeacherSubject.class_id, TeacherSubject.section_id
                ).where(TeacherSubject.teacher_id == teacher.id)
                class_teacher_classes = select(
                    ClassTeacherAssignment.class_id, ClassTeacherAssignment.section_id
                ).where(ClassTeacherAssignment.teacher_id == teacher.id)
                combined = subject_classes.union(class_teacher_classes)
                pairs_result = await db.execute(combined)
                pairs = pairs_result.all()
                if pairs:
                    class_conditions = [
                        (NoticeClassAudience.class_id == p.class_id)
                        & (
                            NoticeClassAudience.section_id.is_(None)
                            | (NoticeClassAudience.section_id == p.section_id)
                        )
                        for p in pairs
                    ]
                    base_query = base_query.where(
                        ~Notice.class_audiences.any()
                        | Notice.class_audiences.any(or_(*class_conditions))
                        | (Notice.created_by == current_user.id)
                    )
                else:
                    base_query = base_query.where(
                        ~Notice.class_audiences.any()
                        | (Notice.created_by == current_user.id)
                    )
        else:
            base_query = base_query.where(~Notice.class_audiences.any())


    if created_by_self:
        base_query = base_query.where(Notice.created_by == current_user.id)

    if exclude_self:
        base_query = base_query.where(Notice.created_by != current_user.id)

    if status_filter:
        base_query = base_query.where(Notice.status == status_filter.value)

    if priority_filter:
        base_query = base_query.where(Notice.priority == priority_filter.value)

    if unread_only:
        base_query = base_query.outerjoin(
            NoticeRead,
            (NoticeRead.notice_id == Notice.id) & (NoticeRead.user_id == current_user.id)
        ).where(NoticeRead.id.is_(None))

    if current_user.role not in ADMIN_VIEWER_ROLES and not created_by_self:
        base_query = base_query.where(
            Notice.status == NoticeStatus.PUBLISHED.value,
            (Notice.publish_at.is_(None)) | (Notice.publish_at <= now),
            (Notice.expires_at.is_(None)) | (Notice.expires_at > now),
        )

    if pinned_only:
        base_query = base_query.where(Notice.is_pinned == True)

    base_query = base_query.order_by(
        Notice.is_pinned.desc(),
        Notice.created_at.desc(),
    )

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(base_query.offset(skip).limit(limit))
    notices = result.scalars().all()

    if notices:
        notice_ids = [n.id for n in notices]
        reads_result = await db.execute(
            select(NoticeRead.notice_id).where(
                NoticeRead.user_id == current_user.id,
                NoticeRead.notice_id.in_(notice_ids),
            )
        )
        read_ids = set(reads_result.scalars().all())
    else:
        read_ids = set()

    unread_query = (
        select(func.count(Notice.id))
        .outerjoin(
            NoticeRead,
            (NoticeRead.notice_id == Notice.id)
            & (NoticeRead.user_id == current_user.id),
        )
        .where(
            Notice.school_id == current_user.school_id,
            Notice.status == NoticeStatus.PUBLISHED.value,
            (Notice.expires_at.is_(None)) | (Notice.expires_at > now),
            (Notice.publish_at.is_(None)) | (Notice.publish_at <= now),
            NoticeRead.id.is_(None),
            Notice.created_by != current_user.id,
        )
    )

    if current_user.role not in ADMIN_VIEWER_ROLES:
        unread_query = unread_query.where(
            ~Notice.audiences.any()
            | Notice.audiences.any(NoticeAudience.role == current_user.role)
        )

    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar_one()

    items = []
    for notice in notices:
        out = NoticeOut.model_validate(notice)
        out.is_read = notice.id in read_ids
        items.append(out)

    return NoticeListOut(items=items, total=total, unread_count=unread_count)


async def update_notice(
    db: AsyncSession, notice_id: int, payload: NoticeUpdate, current_user: User
) -> Notice:
    if not _can_manage(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    result = await db.execute(
        select(Notice)
        .options(selectinload(Notice.audiences))
        .where(
            Notice.id == notice_id,
            Notice.school_id == current_user.school_id,
        )
    )
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notice not found")

    if notice.created_by != current_user.id and current_user.role not in {
        UserRole.SUPER_ADMIN.value,
        UserRole.SCHOOL_OWNER.value,
        UserRole.SCHOOL_ADMIN.value,
    }:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot edit another user's notice")

    for field, value in payload.model_dump(exclude_none=True, exclude={"audience_roles"}).items():
        setattr(notice, field, value.value if hasattr(value, "value") else value)

    if payload.audience_roles is not None:
        await db.execute(
            delete(NoticeAudience).where(NoticeAudience.notice_id == notice.id)
        )
        for role in payload.audience_roles:
            db.add(NoticeAudience(notice_id=notice.id, role=role.value))

    if payload.audience_class_ids is not None:
        if current_user.role == UserRole.TEACHER.value:
            allowed_pairs = await _get_teacher_allowed_pairs(
                db, current_user.id, current_user.school_id
            )
            section_ids = payload.audience_section_ids or []
            submitted = {
                (class_id, section_ids[i] if i < len(section_ids) else None)
                for i, class_id in enumerate(payload.audience_class_ids)
            }
            forbidden = submitted - allowed_pairs
            if forbidden:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You can only target classes/sections you are assigned to",
                )


    await db.commit()
    result = await db.execute(
        select(Notice).options(*_load_options()).where(Notice.id == notice.id)
    )
    return result.scalar_one()


async def pin_notice(
    db: AsyncSession, notice_id: int, is_pinned: bool, current_user: User
) -> Notice:
    """Only admins and above can pin."""
    if current_user.role not in {
        UserRole.SUPER_ADMIN.value,
        UserRole.SCHOOL_OWNER.value,
        UserRole.SCHOOL_ADMIN.value,
    }:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can pin notices")

    result = await db.execute(
        select(Notice).where(
            Notice.id == notice_id,
            Notice.school_id == current_user.school_id,
        )
    )
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notice not found")

    notice.is_pinned = is_pinned
    notice.pinned_by = current_user.id if is_pinned else None
    await db.commit()
    result = await db.execute(
        select(Notice).options(*_load_options()).where(Notice.id == notice.id)
    )
    return result.scalar_one()

async def mark_read(
    db: AsyncSession,
    notice_id: int,
    current_user: User,
) -> dict:
    stmt = (
        insert(NoticeRead)
        .values(
            notice_id=notice_id,
            user_id=current_user.id,
        )
        .on_conflict_do_nothing(
            index_elements=["notice_id", "user_id"]
        )
    )

    await db.execute(stmt)
    await db.commit()

    return {
        "notice_id": notice_id,
        "read": True,
    }

async def delete_notice(
    db: AsyncSession, notice_id: int, current_user: User
) -> None:
    if not _can_manage(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    result = await db.execute(
        select(Notice).where(
            Notice.id == notice_id,
            Notice.school_id == current_user.school_id,
        )
    )
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notice not found")

    if notice.created_by != current_user.id and current_user.role not in {
        UserRole.SUPER_ADMIN.value,
        UserRole.SCHOOL_OWNER.value,
        UserRole.SCHOOL_ADMIN.value,
    }:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete another user's notice")

    await db.delete(notice)
    await db.commit()


async def _get_teacher_allowed_pairs(
    db: AsyncSession, user_id: int, school_id: int
) -> set[tuple[int, int | None]]:
    """
    Returns the set of (class_id, section_id) pairs the teacher is allowed
    to target, from both subject assignments and class-teacher assignments.
    Returns None if the user has no Teacher profile (shouldn't happen but safe).
    """
    result = await db.execute(
        select(Teacher)
        .options(
            selectinload(Teacher.subject_assignments),
            selectinload(Teacher.class_teacher_assignments),
        )
        .where(
            Teacher.user_id == user_id,
            Teacher.school_id == school_id,
            Teacher.is_active.is_(True),
        )
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        return set()

    pairs: set[tuple[int, int | None]] = set()

    for a in teacher.subject_assignments:
        pairs.add((a.class_id, a.section_id))

    for a in teacher.class_teacher_assignments:
        pairs.add((a.class_id, a.section_id))

    return pairs



# helpers

def _check_audience(notice: Notice, user: User) -> None:
    # Admins always pass
    if user.role in {
        UserRole.SUPER_ADMIN.value,
        UserRole.SCHOOL_OWNER.value,
        UserRole.SCHOOL_ADMIN.value,
    }:
        return

    if not notice.audiences:
        return

    allowed = {a.role for a in notice.audiences}
    if user.role not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not in this notice's audience")

    # Check role audience
    if notice.audiences:
        allowed_roles = {a.role for a in notice.audiences}
        if user.role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not in this notice's audience")

    if notice.class_audiences:
        if notice.created_by == user.id:
            return

    if notice.class_audiences:
        user_section_id = getattr(user, "section_id", None)
        user_class_id = getattr(user, "class_id", None)
        allowed_pairs = {(a.class_id, a.section_id) for a in notice.class_audiences}
        if (user_class_id, user_section_id) not in allowed_pairs:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not in this notice's audience")



# AI helpers

async def enhance_notice_content(
    content: str, 
    current_user: User,
    db: AsyncSession,
) -> str:
    """Rewrite an existing notice to be more professional"""
    if not _can_manage(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    
    school_result = await db.execute(
        select(School).where(School.id == current_user.school_id)
    )   
    school = school_result.scalar_one_or_none()
    school_name = school.name if school else "The School"

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    
    response = await client.chat.completions.create(
        model=settings.MODEL,
        messages=[
            {
                "role": "system",
                "content": f"""
                You are a professional notice writer for an educational institution.
                School Name: {school_name}
                Today's Date: {today}
                Issued By: {current_user.full_name or current_user.email}
                Rewrite the given notice to be:
                - Clear and professional
                - Formally structured with proper greeting and closing
                - Concise but complete
                - Appropriate for students and parents
                Return ONLY the rewritten notice, nothing else.
                """
            },
            {"role": "user", "content": content}
        ],
        stream=False
    )
    return response.choices[0].message.content.strip()



async def generate_notice_content(
        description: str, 
        current_user: User,
        db: AsyncSession,
    ) -> str:
    """Generate a full formal notice from a rough description"""
    if not _can_manage(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    school_result = await db.execute(
        select(School).where(School.id == current_user.school_id)
    ) 
    school = school_result.scalar_one_or_none()
    school_name = school.name if school else "The School"

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    
    print(school_name, today)
    response = await client.chat.completions.create(
        model=settings.MODEL,
        messages=[
            {
                "role": "system",
                "content":  f"""You are a professional notice writer for an educational institution.
                School Name: {school_name}
                Today's Date: {today}
                Issued By: {current_user.full_name or current_user.email}
                Based on the admin's rough description, write a complete formal notice that is:
                - Clear and professional
                - Formally structured with proper greeting and closing
                - Concise but complete
                - Appropriate for students and parents
                Return ONLY the notice, nothing else.
                """
            },
            {"role": "user", "content": description}
        ],
        stream=False
    )
    return response.choices[0].message.content.strip()