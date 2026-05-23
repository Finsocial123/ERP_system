from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    progress = Column(Float, default=0.0, nullable=False)

    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course_enrollment"),
    )
