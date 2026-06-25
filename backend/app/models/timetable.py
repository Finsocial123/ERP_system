from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimetablePeriod(Base):
    __tablename__ = "timetable_periods"
    __table_args__ = (
        UniqueConstraint("school_id", "period_number", name="uq_timetable_period_school_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_break: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TimetableDay(Base):
    __tablename__ = "timetable_days"
    __table_args__ = (
        UniqueConstraint("school_id", "day_of_week", name="uq_timetable_day_school_weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "academic_session_id",
            "class_id",
            "section_id",
            "day_id",
            "period_id",
            name="uq_timetable_class_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    academic_session_id: Mapped[int | None] = mapped_column(ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    section_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("timetable_days.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("timetable_periods.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    room: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    academic_session = relationship("AcademicSession")
    school_class = relationship("SchoolClass")
    day = relationship("TimetableDay")
    period = relationship("TimetablePeriod")
    subject = relationship("Subject")
    teacher = relationship("Teacher")
