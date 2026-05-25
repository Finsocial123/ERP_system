from sqlalchemy import (
    Column,
    Integer,
    Float,
    ForeignKey,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.core.database import Base


class VideoWatchProgress(Base):
    __tablename__ = "video_watch_progress"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)

    # Actual credited watch time. This is increased only through small server-validated pings.
    watched_seconds = Column(Float, default=0, nullable=False)

    # Browser-reported duration from the video metadata. Stored so backend can enforce completion.
    video_duration_seconds = Column(Float, default=0, nullable=False)

    # Helpful analytics/debug fields. These do NOT decide completion by themselves.
    max_position_seconds = Column(Float, default=0, nullable=False)
    last_position_seconds = Column(Float, default=0, nullable=False)
    last_watch_ping_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson_video_watch"),
    )
