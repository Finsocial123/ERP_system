from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CommunicationStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class CommunicationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ComplaintStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class Announcement(Base):
    __tablename__ = "communication_announcements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=CommunicationPriority.NORMAL.value, index=True)
    status: Mapped[str] = mapped_column(String(20), default=CommunicationStatus.DRAFT.value, index=True)
    audience_roles: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", foreign_keys=[created_by])


class SchoolEvent(Base):
    __tablename__ = "communication_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=CommunicationStatus.PUBLISHED.value, index=True)
    audience_roles: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", foreign_keys=[created_by])


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default=CommunicationPriority.NORMAL.value, index=True)
    status: Mapped[str] = mapped_column(String(30), default=ComplaintStatus.SUBMITTED.value, index=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_role: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default=CommunicationPriority.NORMAL.value, index=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    author = relationship("User", foreign_keys=[created_by])
    target_user = relationship("User", foreign_keys=[target_user_id])
    reads = relationship("InAppNotificationRead", back_populates="notification", cascade="all, delete-orphan")


class InAppNotificationRead(Base):
    __tablename__ = "in_app_notification_reads"
    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_notification_read_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("in_app_notifications.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    notification = relationship("InAppNotification", back_populates="reads")
    user = relationship("User")
