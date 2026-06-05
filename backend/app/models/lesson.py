from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from pgvector.sqlalchemy import Vector
from app.models.progress import LessonProgress


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, default=1)

    video_url = Column(String(500), nullable=True)
    pdf_url = Column(String(500), nullable=True)
    external_video_link = Column(String(500), nullable=True)
    transcript = Column(Text, nullable=True)         # raw transcript using whisper
    notes = Column(Text, nullable=True)              # text content
    chunks = relationship("LessonChunk", back_populates="lesson", cascade="all, delete-orphan")

    # Cloudinary public_ids for deletion
    video_public_id = Column(String(255), nullable=True)
    pdf_public_id = Column(String(255), nullable=True)

    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    
    progress_records = relationship(
        "LessonProgress",
        backref="lesson",
        cascade="all, delete-orphan"
    )
    summary: Mapped[str] = mapped_column(Text, nullable=True)


class LessonChunk(Base):
    __tablename__ = "lesson_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "notes" or "transcript"
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))

    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    lesson: Mapped["Lesson"] = relationship(back_populates="chunks")

