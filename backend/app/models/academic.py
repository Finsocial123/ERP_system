from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AcademicSession(Base):
    __tablename__ = "academic_sessions"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_session_school_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_department_school_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SchoolClass(Base):
    __tablename__ = "school_classes"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_class_school_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    department = relationship("Department")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("school_id", "class_id", "name", name="uq_section_school_class_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    school_class = relationship("SchoolClass")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_subject_school_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    department = relationship("Department")
    school_class = relationship("SchoolClass")
