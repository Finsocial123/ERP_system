from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.enrollment import Enrollment
from app.models.assignment import Assignment
from app.models.submission import Submission

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    teacher = relationship("User", backref="courses")
    lessons = relationship(
        "Lesson",
        backref="course",
        cascade="all, delete-orphan"
    )
    enrollments = relationship(
        "Enrollment",
        backref="course",
        cascade="all, delete-orphan"
    )
    assignments = relationship(
        "Assignment",
        backref="course",
        cascade="all, delete-orphan"
    )