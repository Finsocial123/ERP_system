from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from app.core.database import get_async_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.library import Book, BookIssue, IssueStatus
from app.models.people import Student, Teacher
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.library import BookCreate, BookRead, BookUpdate, IssueCreate, IssueRead, LibraryStats, MarkFinePaid, ReturnBook
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.async_query import async_query
router = APIRouter(prefix='/library', tags=['Phase 11 - Library'])
ADMIN_ROLES = [UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN]
STAFF_ROLES = [UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER]

async def _get_book_or_404(db: AsyncSession, book_id: int, school_id: int) -> Book:
    book = await async_query(db, Book).filter(Book.id == book_id, Book.school_id == school_id).first()
    if not book:
        raise HTTPException(status_code=404, detail='Book not found')
    return book

async def _get_issue_or_404(db: AsyncSession, issue_id: int, school_id: int) -> BookIssue:
    issue = await async_query(db, BookIssue).filter(BookIssue.id == issue_id, BookIssue.school_id == school_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail='Issue record not found')
    return issue

def _calc_fine(issue: BookIssue, as_of: date) -> int:
    if issue.return_date:
        ref = issue.return_date
    else:
        ref = as_of
    if ref > issue.due_date:
        return (ref - issue.due_date).days * issue.fine_per_day
    return 0

def _issue_to_read(issue: BookIssue, today: date) -> IssueRead:
    fine = _calc_fine(issue, today)
    overdue_days = max(0, (today - issue.due_date).days) if issue.status == IssueStatus.ISSUED.value else 0
    return IssueRead(id=issue.id, book_id=issue.book_id, book_title=issue.book.title if issue.book else '', book_isbn=issue.book.isbn if issue.book else None, student_id=issue.student_id, teacher_id=issue.teacher_id, borrower_name=issue.borrower_name, issue_date=issue.issue_date, due_date=issue.due_date, return_date=issue.return_date, status=issue.status, fine_per_day=issue.fine_per_day, fine_amount=fine, fine_paid=issue.fine_paid, notes=issue.notes, days_overdue=overdue_days)

@router.post('/books', response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def add_book(payload: BookCreate, school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    if payload.isbn:
        exists = await async_query(db, Book).filter(Book.school_id == school_id, Book.isbn == payload.isbn).first()
        if exists:
            raise HTTPException(status_code=409, detail='A book with this ISBN already exists')
    book = Book(school_id=school_id, available_copies=payload.total_copies, **payload.model_dump())
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book

@router.get('/books', response_model=list[BookRead])
async def list_books(search: str | None=Query(default=None), category: str | None=Query(default=None), available_only: bool=Query(default=False), skip: int=Query(default=0, ge=0), limit: int=Query(default=50, le=200), school_id: int=Depends(current_school_id), _: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    q = async_query(db, Book).filter(Book.school_id == school_id, Book.is_active.is_(True))
    if search:
        term = f'%{search}%'
        q = q.filter(or_(Book.title.ilike(term), Book.author.ilike(term), Book.isbn.ilike(term)))
    if category:
        q = q.filter(Book.category == category)
    if available_only:
        q = q.filter(Book.available_copies > 0)
    return await q.order_by(Book.title).offset(skip).limit(limit).all()

@router.get('/books/{book_id}', response_model=BookRead)
async def get_book(book_id: int, school_id: int=Depends(current_school_id), _: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    return await _get_book_or_404(db, book_id, school_id)

@router.patch('/books/{book_id}', response_model=BookRead)
async def update_book(book_id: int, payload: BookUpdate, school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    book = await _get_book_or_404(db, book_id, school_id)
    data = payload.model_dump(exclude_unset=True)
    if 'total_copies' in data:
        issued = book.total_copies - book.available_copies
        new_available = max(0, data['total_copies'] - issued)
        book.available_copies = new_available
    for k, v in data.items():
        setattr(book, k, v)
    await db.commit()
    await db.refresh(book)
    return book

@router.delete('/books/{book_id}', response_model=MessageResponse)
async def delete_book(book_id: int, school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*ADMIN_ROLES)), db: AsyncSession=Depends(get_async_db)):
    book = await _get_book_or_404(db, book_id, school_id)
    active_issues = await async_query(db, BookIssue).filter(BookIssue.book_id == book_id, BookIssue.status == IssueStatus.ISSUED.value).count()
    if active_issues > 0:
        raise HTTPException(status_code=400, detail=f'Cannot delete — {active_issues} copy/copies currently issued')
    book.is_active = False
    await db.commit()
    return MessageResponse(message='Book deactivated successfully')

@router.get('/categories', response_model=list[str])
async def list_categories(school_id: int=Depends(current_school_id), _: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    rows = await async_query(db, Book.category).filter(Book.school_id == school_id, Book.is_active.is_(True), Book.category.isnot(None)).distinct().order_by(Book.category).all()
    return [r[0] for r in rows]

@router.post('/issues', response_model=IssueRead, status_code=status.HTTP_201_CREATED)
async def issue_book(payload: IssueCreate, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    if not payload.student_id and (not payload.teacher_id):
        raise HTTPException(status_code=400, detail='Provide either student_id or teacher_id')
    if payload.due_date <= payload.issue_date:
        raise HTTPException(status_code=400, detail='due_date must be after issue_date')
    book = await _get_book_or_404(db, payload.book_id, school_id)
    if not book.is_active:
        raise HTTPException(status_code=400, detail='Book is not active')
    if book.available_copies < 1:
        raise HTTPException(status_code=400, detail='No copies available for this book')
    borrower_name = 'Unknown'
    if payload.student_id:
        student = await async_query(db, Student).filter(Student.id == payload.student_id, Student.school_id == school_id).first()
        if not student:
            raise HTTPException(status_code=404, detail='Student not found')
        borrower_name = f"{student.first_name} {student.last_name or ''}".strip()
    elif payload.teacher_id:
        teacher = await async_query(db, Teacher).filter(Teacher.id == payload.teacher_id, Teacher.school_id == school_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail='Teacher not found')
        borrower_name = teacher.full_name
    issue = BookIssue(school_id=school_id, book_id=payload.book_id, student_id=payload.student_id, teacher_id=payload.teacher_id, borrower_name=borrower_name, issued_by=current_user.id, issue_date=payload.issue_date, due_date=payload.due_date, fine_per_day=payload.fine_per_day, notes=payload.notes, status=IssueStatus.ISSUED.value)
    book.available_copies -= 1
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return _issue_to_read(issue, date.today())

@router.post('/issues/{issue_id}/return', response_model=IssueRead)
async def return_book(issue_id: int, payload: ReturnBook, school_id: int=Depends(current_school_id), current_user: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    issue = await _get_issue_or_404(db, issue_id, school_id)
    if issue.status not in {IssueStatus.ISSUED.value, IssueStatus.OVERDUE.value}:
        raise HTTPException(status_code=400, detail='This book is not currently issued')
    issue.return_date = payload.return_date
    issue.returned_to = current_user.id
    issue.notes = payload.notes or issue.notes
    if payload.mark_lost:
        issue.status = IssueStatus.LOST.value
    else:
        issue.status = IssueStatus.RETURNED.value
        issue.book.available_copies += 1
    if payload.fine_override is not None:
        issue.fine_amount = payload.fine_override
    else:
        issue.fine_amount = _calc_fine(issue, payload.return_date)
    await db.commit()
    await db.refresh(issue)
    return _issue_to_read(issue, date.today())

@router.post('/issues/{issue_id}/pay-fine', response_model=IssueRead)
async def mark_fine_paid(issue_id: int, payload: MarkFinePaid, school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    issue = await _get_issue_or_404(db, issue_id, school_id)
    issue.fine_paid = payload.fine_paid
    await db.commit()
    await db.refresh(issue)
    return _issue_to_read(issue, date.today())

@router.get('/issues', response_model=list[IssueRead])
async def list_issues(status_filter: str | None=Query(default=None, alias='status'), student_id: int | None=Query(default=None), teacher_id: int | None=Query(default=None), book_id: int | None=Query(default=None), skip: int=Query(default=0, ge=0), limit: int=Query(default=50, le=200), school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    today = date.today()
    await async_query(db, BookIssue).filter(BookIssue.school_id == school_id, BookIssue.status == IssueStatus.ISSUED.value, BookIssue.due_date < today).update({'status': IssueStatus.OVERDUE.value})
    await db.commit()
    q = async_query(db, BookIssue).filter(BookIssue.school_id == school_id)
    if status_filter:
        q = q.filter(BookIssue.status == status_filter.upper())
    if student_id:
        q = q.filter(BookIssue.student_id == student_id)
    if teacher_id:
        q = q.filter(BookIssue.teacher_id == teacher_id)
    if book_id:
        q = q.filter(BookIssue.book_id == book_id)
    issues = await q.order_by(BookIssue.issue_date.desc()).offset(skip).limit(limit).all()
    return [_issue_to_read(i, today) for i in issues]

@router.get('/issues/overdue', response_model=list[IssueRead])
async def overdue_issues(school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    today = date.today()
    
    issues = await async_query(db, BookIssue)\
        .options(
            selectinload(BookIssue.book)
        )\
        .filter(
            BookIssue.school_id == school_id,
            BookIssue.status.in_(
                [IssueStatus.ISSUED.value, IssueStatus.OVERDUE.value]
            ),
            BookIssue.due_date < today
        )\
        .order_by(BookIssue.due_date)\
        .all()
    return [_issue_to_read(i, today) for i in issues]

@router.get('/issues/my', response_model=list[IssueRead])
async def my_issues(school_id: int=Depends(current_school_id), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    today = date.today()
    student = await async_query(db, Student).filter(Student.user_id == current_user.id, Student.school_id == school_id).first()
    teacher = await async_query(db, Teacher).filter(Teacher.user_id == current_user.id, Teacher.school_id == school_id).first()
    q = async_query(db, BookIssue).filter(BookIssue.school_id == school_id)
    if student:
        q = q.filter(BookIssue.student_id == student.id)
    elif teacher:
        q = q.filter(BookIssue.teacher_id == teacher.id)
    else:
        return []
    issues = await q.order_by(BookIssue.issue_date.desc()).all()
    return [_issue_to_read(i, today) for i in issues]

@router.get('/issues/{issue_id}', response_model=IssueRead)
async def get_issue(issue_id: int, school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    issue = await _get_issue_or_404(db, issue_id, school_id)
    return _issue_to_read(issue, date.today())

@router.get('/stats', response_model=LibraryStats)
async def library_stats(school_id: int=Depends(current_school_id), _: User=Depends(require_roles(*STAFF_ROLES)), db: AsyncSession=Depends(get_async_db)):
    today = date.today()
    total_books = await async_query(db, Book).filter(Book.school_id == school_id, Book.is_active.is_(True)).count()
    copies_q = await async_query(db, Book).filter(Book.school_id == school_id, Book.is_active.is_(True)).all()
    total_copies = sum((b.total_copies for b in copies_q))
    available_copies = sum((b.available_copies for b in copies_q))
    issued_count = await async_query(db, BookIssue).filter(BookIssue.school_id == school_id, BookIssue.status.in_([IssueStatus.ISSUED.value, IssueStatus.OVERDUE.value])).count()
    overdue_count = await async_query(db, BookIssue).filter(BookIssue.school_id == school_id, BookIssue.status.in_([IssueStatus.ISSUED.value, IssueStatus.OVERDUE.value]), BookIssue.due_date < today).count()
    pending_fines = await async_query(db, BookIssue).filter(BookIssue.school_id == school_id, BookIssue.fine_paid.is_(False), BookIssue.status.in_([IssueStatus.RETURNED.value, IssueStatus.OVERDUE.value, IssueStatus.LOST.value])).all()
    total_fine = sum((_calc_fine(i, today) for i in pending_fines))
    return LibraryStats(total_books=total_books, total_copies=total_copies, available_copies=available_copies, issued_count=issued_count, overdue_count=overdue_count, total_fine_pending=total_fine)
