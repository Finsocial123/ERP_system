from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.assignment import Assignment
from app.models.enrollment import Enrollment
from app.models.submission import Submission  # noqa: F401 - keeps legacy LMS submission model registered


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    section_name = Column(String(80), nullable=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    # Owner user account. For ERP teacher profile lookup use Teacher.user_id.
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(30), default="PUBLISHED", nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    school = relationship("School")
    school_class = relationship("SchoolClass")
    subject = relationship("Subject")
    academic_session = relationship("AcademicSession")
    teacher = relationship("User", backref="courses")
    lessons = relationship("Lesson", backref="course", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", backref="course", cascade="all, delete-orphan")
    assignments = relationship("Assignment", backref="course", cascade="all, delete-orphan")
