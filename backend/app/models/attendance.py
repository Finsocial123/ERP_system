from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"
    HALF_DAY = "HALF_DAY"


class StudentAttendance(Base):
    __tablename__ = "student_attendance"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "student_id", "date", "session_id",
            name="uq_student_attendance_per_day",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    section_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    marked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AttendanceStatus.PRESENT.value, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student")
    school_class = relationship("SchoolClass")
    session = relationship("AcademicSession")
    marker = relationship("User")
