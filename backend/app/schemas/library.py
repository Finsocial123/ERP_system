from datetime import date

from pydantic import BaseModel, Field


# ── Book schemas ─────────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(min_length=1, max_length=200)
    isbn: str | None = Field(default=None, max_length=30)
    publisher: str | None = Field(default=None, max_length=200)
    edition: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=100)
    language: str = Field(default="English", max_length=60)
    shelf_location: str | None = Field(default=None, max_length=100)
    description: str | None = None
    cover_url: str | None = Field(default=None, max_length=500)
    total_copies: int = Field(default=1, ge=1)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    author: str | None = Field(default=None, min_length=1, max_length=200)
    isbn: str | None = Field(default=None, max_length=30)
    publisher: str | None = Field(default=None, max_length=200)
    edition: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=60)
    shelf_location: str | None = Field(default=None, max_length=100)
    description: str | None = None
    cover_url: str | None = Field(default=None, max_length=500)
    total_copies: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class BookRead(BaseModel):
    id: int
    title: str
    author: str
    isbn: str | None = None
    publisher: str | None = None
    edition: str | None = None
    category: str | None = None
    language: str
    shelf_location: str | None = None
    description: str | None = None
    cover_url: str | None = None
    total_copies: int
    available_copies: int
    is_active: bool

    model_config = {"from_attributes": True}


# ── Issue schemas ─────────────────────────────────────────────────────────────

class IssueCreate(BaseModel):
    book_id: int
    student_id: int | None = None
    teacher_id: int | None = None
    issue_date: date
    due_date: date
    fine_per_day: int = Field(default=1, ge=0)
    notes: str | None = None


class ReturnBook(BaseModel):
    return_date: date
    notes: str | None = None
    mark_lost: bool = False
    fine_override: int | None = Field(default=None, ge=0)


class MarkFinePaid(BaseModel):
    fine_paid: bool = True


class IssueRead(BaseModel):
    id: int
    book_id: int
    book_title: str
    book_isbn: str | None = None
    student_id: int | None = None
    teacher_id: int | None = None
    borrower_name: str
    issue_date: date
    due_date: date
    return_date: date | None = None
    status: str
    fine_per_day: int
    fine_amount: int
    fine_paid: bool
    notes: str | None = None
    days_overdue: int = 0

    model_config = {"from_attributes": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

class LibraryStats(BaseModel):
    total_books: int
    total_copies: int
    available_copies: int
    issued_count: int
    overdue_count: int
    total_fine_pending: int
