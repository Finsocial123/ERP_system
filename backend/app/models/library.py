from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BookStatus(str, Enum):
    AVAILABLE  = "AVAILABLE"
    ISSUED     = "ISSUED"
    LOST       = "LOST"
    DAMAGED    = "DAMAGED"


class IssueStatus(str, Enum):
    ISSUED   = "ISSUED"
    RETURNED = "RETURNED"
    OVERDUE  = "OVERDUE"
    LOST     = "LOST"


class Book(Base):
    __tablename__ = "library_books"
    __table_args__ = (
        UniqueConstraint("school_id", "isbn", name="uq_book_isbn_school"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    edition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(60), default="English")
    shelf_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    total_copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    available_copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    issues = relationship("BookIssue", back_populates="book")


class BookIssue(Base):
    __tablename__ = "library_issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("library_books.id", ondelete="CASCADE"), index=True)

    # borrower — one of these will be set
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    # for staff/admin who don't have a teacher record
    issued_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    borrower_name: Mapped[str] = mapped_column(String(200), nullable=False)  # denormalized for display

    issued_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    returned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=IssueStatus.ISSUED.value, index=True)

    fine_per_day: Mapped[int] = mapped_column(Integer, default=1)   # in rupees
    fine_amount: Mapped[int] = mapped_column(Integer, default=0)
    fine_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book = relationship("Book", back_populates="issues",  lazy="selectin")
    student = relationship("Student",  lazy="selectin")
    teacher = relationship("Teacher",  lazy="selectin")
