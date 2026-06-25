# app/models/bbb_meeting.py
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base


class MeetingType(str, enum.Enum):
    TEACHER_CLASS = "teacher_class"
    ADMIN_TEACHERS = "admin_teachers"


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"


_enum_values = lambda x: [e.value for e in x]


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    bbb_meeting_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    attendee_password: Mapped[str | None] = mapped_column(String(100), nullable=True)
    moderator_password: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    meeting_type: Mapped[MeetingType] = mapped_column(
        SAEnum(MeetingType, values_callable=_enum_values, name="meetingtype"),
        nullable=False,
    )
    status: Mapped[MeetingStatus] = mapped_column(
        SAEnum(MeetingStatus, values_callable=_enum_values, name="meetingstatus"),
        default=MeetingStatus.LIVE,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True, index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    section_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    record: Mapped[bool] = mapped_column(Boolean, default=True)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
)

    school_class = relationship("SchoolClass")
    teacher = relationship("Teacher")
    created_by = relationship("User")