from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, UniqueConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NoticePriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class NoticeStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20), default=NoticePriority.NORMAL.value, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=NoticeStatus.DRAFT.value, index=True
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    author = relationship("User", foreign_keys=[created_by])
    pinner = relationship("User", foreign_keys=[pinned_by])
    audiences = relationship(
        "NoticeAudience", back_populates="notice", cascade="all, delete-orphan"
    )
    reads = relationship(
        "NoticeRead", back_populates="notice", cascade="all, delete-orphan"
    )
    class_audiences = relationship(
        "NoticeClassAudience", back_populates="notice", cascade="all, delete-orphan"
    )

class NoticeAudience(Base):
    __tablename__ = "notice_audiences"
    __table_args__ = (
        UniqueConstraint("notice_id", "role", name="uq_notice_audience_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    notice = relationship("Notice", back_populates="audiences")

class NoticeRead(Base):
    __tablename__ = "notice_reads"
    __table_args__ = (
        UniqueConstraint("notice_id", "user_id", name="uq_notice_read_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    notice = relationship("Notice", back_populates="reads")
    user = relationship("User")


class NoticeClassAudience(Base):
    __tablename__ = "notice_class_audiences"
    __table_args__ = (
        UniqueConstraint("notice_id", "class_id", "section_id", name="uq_notice_class_section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), nullable=True, index=True
    )
    section_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    notice = relationship("Notice", back_populates="class_audiences")