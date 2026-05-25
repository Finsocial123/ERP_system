from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.academic import AcademicSession, SchoolClass, Section
from app.models.fee import FeeAssignment, FeeCategory, FeeExpense, FeePayment, FeeStructure, StudentFeeRecord
from app.models.people import ParentGuardian, Student
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.fee import (
    DailyCollectionReport,
    FeeAssignmentCreate,
    FeeAssignmentRead,
    FeeAssignmentUpdate,
    FeeCategoryCreate,
    FeeCategoryRead,
    FeeCategoryUpdate,
    FeeDashboardRead,
    FeeExpenseCreate,
    FeeExpenseRead,
    FeeExpenseUpdate,
    FeeMetaItem,
    FeeMetaResponse,
    FeePaymentCreate,
    FeePaymentRead,
    FeePortalResponse,
    FeeReceiptRead,
    FeeStructureCreate,
    FeeStructureRead,
    FeeStructureUpdate,
    StudentFeeRecordCreate,
    StudentFeeRecordRead,
    StudentFeeRecordUpdate,
)

router = APIRouter(prefix="/fees", tags=["Phase 6 - Fee Management"])

ADMIN_ROLES = (UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value)
PAYMENT_MODES = {"CASH", "UPI", "CARD", "BANK_TRANSFER", "CHEQUE", "ONLINE", "OTHER"}
PENDING_STATUSES = {"PENDING", "PARTIAL", "OVERDUE"}


def _money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def _full_student_name(student: Student | None) -> str | None:
    if not student:
        return None
    return f"{student.first_name} {student.last_name or ''}".strip()


def _current_session(db: Session, school_id: int) -> AcademicSession | None:
    today = date.today()
    active = (
        db.query(AcademicSession)
        .filter(AcademicSession.school_id == school_id, AcademicSession.is_active.is_(True))
        .order_by(AcademicSession.id.desc())
        .first()
    )
    if active:
        return active
    by_date = (
        db.query(AcademicSession)
        .filter(AcademicSession.school_id == school_id, AcademicSession.start_date <= today, AcademicSession.end_date >= today)
        .order_by(AcademicSession.id.desc())
        .first()
    )
    if by_date:
        return by_date
    return db.query(AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).first()


def _get_or_404(db: Session, model, item_id: int | None, school_id: int, name: str):
    if item_id is None:
        return None
    item = db.query(model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{name} not found for this school")
    return item


def _student_for_user(db: Session, school_id: int, user: User) -> Student | None:
    student = db.query(Student).filter(Student.school_id == school_id, Student.user_id == user.id).first()
    if student:
        return student

    conditions = []
    if user.email:
        conditions.append(Student.email == user.email)
    if user.phone:
        conditions.append(Student.phone == user.phone)
    if user.login_id:
        conditions.append(Student.admission_no == user.login_id)
    if not conditions:
        return None

    return db.query(Student).filter(Student.school_id == school_id, Student.is_active.is_(True), or_(*conditions)).first()


def _children_for_parent(db: Session, school_id: int, user: User) -> list[Student]:
    conditions = [ParentGuardian.user_id == user.id]
    if user.email:
        conditions.append(ParentGuardian.email == user.email)
    if user.phone:
        conditions.append(ParentGuardian.phone == user.phone)

    guardians = (
        db.query(ParentGuardian)
        .filter(ParentGuardian.school_id == school_id, ParentGuardian.is_active.is_(True), or_(*conditions))
        .all()
    )
    guardian_ids = [guardian.id for guardian in guardians]
    if not guardian_ids:
        return []

    return (
        db.query(Student)
        .filter(Student.school_id == school_id, Student.guardian_id.in_(guardian_ids), Student.is_active.is_(True))
        .order_by(Student.first_name.asc())
        .all()
    )


def _validate_payment_mode(payment_mode: str) -> str:
    normalized = (payment_mode or "CASH").strip().upper().replace(" ", "_")
    if normalized not in PAYMENT_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid payment mode. Use one of: {', '.join(sorted(PAYMENT_MODES))}")
    return normalized


def _recalculate_record(record: StudentFeeRecord) -> None:
    billable = _money(record.amount + record.fine_amount - record.discount_amount)
    if billable < 0:
        billable = 0
    balance = _money(billable - record.paid_amount)
    record.balance_amount = max(balance, 0)

    if record.status == "WAIVED":
        record.balance_amount = 0
        return
    if record.balance_amount <= 0:
        record.status = "PAID"
    elif record.paid_amount > 0:
        record.status = "PARTIAL"
    elif record.due_date and record.due_date < date.today():
        record.status = "OVERDUE"
    else:
        record.status = "PENDING"


def _receipt_number(db: Session, school_id: int, payment_date: date) -> str:
    date_part = payment_date.strftime("%Y%m%d")
    start = datetime.combine(payment_date, datetime.min.time())
    end = start + timedelta(days=1)
    today_count = (
        db.query(FeePayment)
        .filter(FeePayment.school_id == school_id, FeePayment.created_at >= start, FeePayment.created_at < end)
        .count()
    )
    return f"FEE-{date_part}-{school_id:03d}-{today_count + 1:04d}"


def _validate_category(db: Session, school_id: int, category_id: int) -> FeeCategory:
    category = _get_or_404(db, FeeCategory, category_id, school_id, "Fee category")
    if not category.is_active:
        raise HTTPException(status_code=400, detail="Selected fee category is inactive")
    return category


def _validate_structure(db: Session, school_id: int, structure_id: int | None) -> FeeStructure | None:
    structure = _get_or_404(db, FeeStructure, structure_id, school_id, "Fee structure")
    if structure and not structure.is_active:
        raise HTTPException(status_code=400, detail="Selected fee structure is inactive")
    return structure


def _validate_student_scope(db: Session, school_id: int, student_id: int) -> Student:
    student = _get_or_404(db, Student, student_id, school_id, "Student")
    if not student.is_active:
        raise HTTPException(status_code=400, detail="Selected student is inactive")
    return student


def _validate_class_scope(db: Session, school_id: int, class_id: int | None, section_id: int | None) -> tuple[SchoolClass | None, Section | None]:
    school_class = _get_or_404(db, SchoolClass, class_id, school_id, "Class")
    section = _get_or_404(db, Section, section_id, school_id, "Section")
    if school_class and not school_class.is_active:
        raise HTTPException(status_code=400, detail="Selected class is inactive")
    if section and section.class_id != class_id:
        raise HTTPException(status_code=400, detail="Selected section does not belong to selected class")
    return school_class, section


def _category_read(category: FeeCategory) -> FeeCategoryRead:
    return FeeCategoryRead(
        id=category.id,
        name=category.name,
        code=category.code,
        description=category.description,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _structure_read(structure: FeeStructure) -> FeeStructureRead:
    return FeeStructureRead(
        id=structure.id,
        name=structure.name,
        category_id=structure.category_id,
        category_name=structure.category.name if structure.category else None,
        academic_session_id=structure.academic_session_id,
        academic_session_name=structure.academic_session.name if structure.academic_session else None,
        amount=_money(structure.amount),
        due_date=structure.due_date,
        description=structure.description,
        is_active=structure.is_active,
        created_at=structure.created_at,
        updated_at=structure.updated_at,
    )


def _assignment_read(db: Session, assignment: FeeAssignment) -> FeeAssignmentRead:
    return FeeAssignmentRead(
        id=assignment.id,
        fee_structure_id=assignment.fee_structure_id,
        fee_structure_name=assignment.fee_structure.name if assignment.fee_structure else None,
        academic_session_id=assignment.academic_session_id,
        academic_session_name=assignment.academic_session.name if assignment.academic_session else None,
        class_id=assignment.class_id,
        class_name=assignment.school_class.name if assignment.school_class else None,
        section_id=assignment.section_id,
        section_name=assignment.section.name if assignment.section else None,
        student_id=assignment.student_id,
        student_name=_full_student_name(assignment.student),
        assigned_amount=_money(assignment.assigned_amount) if assignment.assigned_amount is not None else None,
        due_date=assignment.due_date,
        note=assignment.note,
        is_active=assignment.is_active,
        generated_records_count=db.query(StudentFeeRecord).filter(StudentFeeRecord.school_id == assignment.school_id, StudentFeeRecord.fee_assignment_id == assignment.id).count(),
        generated_at=assignment.generated_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _record_read(record: StudentFeeRecord) -> StudentFeeRecordRead:
    student = record.student
    return StudentFeeRecordRead(
        id=record.id,
        student_id=record.student_id,
        student_name=_full_student_name(student),
        admission_no=student.admission_no if student else None,
        roll_number=student.roll_number if student else None,
        class_name=student.school_class.name if student and student.school_class else None,
        section_name=student.section.name if student and student.section else None,
        fee_structure_id=record.fee_structure_id,
        fee_structure_name=record.fee_structure.name if record.fee_structure else None,
        fee_assignment_id=record.fee_assignment_id,
        academic_session_id=record.academic_session_id,
        academic_session_name=record.academic_session.name if record.academic_session else None,
        title=record.title,
        amount=_money(record.amount),
        discount_amount=_money(record.discount_amount),
        fine_amount=_money(record.fine_amount),
        paid_amount=_money(record.paid_amount),
        balance_amount=_money(record.balance_amount),
        due_date=record.due_date,
        status=record.status,
        note=record.note,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _payment_read(payment: FeePayment) -> FeePaymentRead:
    student = payment.student
    record = payment.student_fee_record
    return FeePaymentRead(
        id=payment.id,
        student_fee_record_id=payment.student_fee_record_id,
        student_id=payment.student_id,
        student_name=_full_student_name(student),
        admission_no=student.admission_no if student else None,
        fee_title=record.title if record else None,
        receipt_no=payment.receipt_no,
        amount=_money(payment.amount),
        payment_date=payment.payment_date,
        payment_mode=payment.payment_mode,
        reference_no=payment.reference_no,
        note=payment.note,
        collected_by_user_id=payment.collected_by_user_id,
        collected_by_name=payment.collected_by.full_name if payment.collected_by else None,
        created_at=payment.created_at,
    )


def _expense_read(expense: FeeExpense) -> FeeExpenseRead:
    return FeeExpenseRead(
        id=expense.id,
        title=expense.title,
        category=expense.category,
        amount=_money(expense.amount),
        expense_date=expense.expense_date,
        payment_mode=expense.payment_mode,
        vendor_name=expense.vendor_name,
        reference_no=expense.reference_no,
        note=expense.note,
        is_active=expense.is_active,
        created_by_user_id=expense.created_by_user_id,
        created_by_name=expense.created_by.full_name if expense.created_by else None,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


def _records_query(db: Session, school_id: int):
    return db.query(StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id)


def _payment_query(db: Session, school_id: int):
    return db.query(FeePayment).filter(FeePayment.school_id == school_id)


def _dashboard_summary(db: Session, school_id: int, student_ids: list[int] | None = None) -> FeeDashboardRead:
    records_query = _records_query(db, school_id)
    payments_query = _payment_query(db, school_id)
    expenses_query = db.query(FeeExpense).filter(FeeExpense.school_id == school_id, FeeExpense.is_active.is_(True))

    if student_ids is not None:
        if not student_ids:
            records_query = records_query.filter(StudentFeeRecord.id == -1)
            payments_query = payments_query.filter(FeePayment.id == -1)
            expenses_query = expenses_query.filter(FeeExpense.id == -1)
        else:
            records_query = records_query.filter(StudentFeeRecord.student_id.in_(student_ids))
            payments_query = payments_query.filter(FeePayment.student_id.in_(student_ids))
            expenses_query = expenses_query.filter(FeeExpense.id == -1)

    today = date.today()
    month_start = today.replace(day=1)

    records = records_query.all()
    total_billable = sum(_money(record.amount + record.fine_amount - record.discount_amount) for record in records)
    total_paid = sum(_money(record.paid_amount) for record in records)
    total_pending = sum(_money(record.balance_amount) for record in records if record.status in PENDING_STATUSES)

    today_collection = _money(payments_query.filter(FeePayment.payment_date == today).with_entities(func.coalesce(func.sum(FeePayment.amount), 0)).scalar())
    month_collection = _money(payments_query.filter(FeePayment.payment_date >= month_start).with_entities(func.coalesce(func.sum(FeePayment.amount), 0)).scalar())
    month_expense = _money(expenses_query.filter(FeeExpense.expense_date >= month_start).with_entities(func.coalesce(func.sum(FeeExpense.amount), 0)).scalar())

    return FeeDashboardRead(
        total_records=len(records),
        pending_records=len([record for record in records if record.status == "PENDING"]),
        partial_records=len([record for record in records if record.status == "PARTIAL"]),
        paid_records=len([record for record in records if record.status == "PAID"]),
        overdue_records=len([record for record in records if record.status == "OVERDUE"]),
        total_billable=_money(total_billable),
        total_paid=_money(total_paid),
        total_pending=_money(total_pending),
        today_collection=today_collection,
        month_collection=month_collection,
        month_expense=month_expense,
        net_month_collection=_money(month_collection - month_expense),
    )


def _students_for_assignment(db: Session, school_id: int, assignment: FeeAssignment) -> list[Student]:
    if assignment.student_id:
        student = _validate_student_scope(db, school_id, assignment.student_id)
        return [student]

    if not assignment.class_id:
        return []

    query = db.query(Student).filter(Student.school_id == school_id, Student.class_id == assignment.class_id, Student.is_active.is_(True))
    if assignment.section_id:
        query = query.filter(Student.section_id == assignment.section_id)
    return query.order_by(Student.roll_number.asc(), Student.first_name.asc()).all()


def _generate_records_for_assignment(db: Session, school_id: int, assignment: FeeAssignment) -> int:
    structure = assignment.fee_structure
    if not structure:
        return 0

    students = _students_for_assignment(db, school_id, assignment)
    amount = assignment.assigned_amount if assignment.assigned_amount is not None else structure.amount
    due_date = assignment.due_date or structure.due_date
    generated = 0

    for student in students:
        existing = (
            db.query(StudentFeeRecord)
            .filter(
                StudentFeeRecord.school_id == school_id,
                StudentFeeRecord.student_id == student.id,
                StudentFeeRecord.fee_assignment_id == assignment.id,
            )
            .first()
        )
        if existing:
            continue

        record = StudentFeeRecord(
            school_id=school_id,
            student_id=student.id,
            fee_structure_id=structure.id,
            fee_assignment_id=assignment.id,
            academic_session_id=assignment.academic_session_id or structure.academic_session_id,
            title=structure.name,
            amount=_money(amount),
            discount_amount=0,
            fine_amount=0,
            paid_amount=0,
            balance_amount=_money(amount),
            due_date=due_date,
            status="PENDING",
            note=assignment.note,
        )
        _recalculate_record(record)
        db.add(record)
        generated += 1

    assignment.generated_at = datetime.utcnow()
    return generated


def _authorized_student_ids(db: Session, school_id: int, current_user: User) -> list[int]:
    if current_user.role == UserRole.STUDENT.value:
        student = _student_for_user(db, school_id, current_user)
        return [student.id] if student else []
    if current_user.role == UserRole.PARENT.value:
        return [student.id for student in _children_for_parent(db, school_id, current_user)]
    return []


@router.get("/meta", response_model=FeeMetaResponse)
def fee_meta(
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    current_session = _current_session(db, school_id)
    categories = db.query(FeeCategory).filter(FeeCategory.school_id == school_id, FeeCategory.is_active.is_(True)).order_by(FeeCategory.name.asc()).all()
    structures = db.query(FeeStructure).filter(FeeStructure.school_id == school_id, FeeStructure.is_active.is_(True)).order_by(FeeStructure.name.asc()).all()
    classes = db.query(SchoolClass).filter(SchoolClass.school_id == school_id, SchoolClass.is_active.is_(True)).order_by(SchoolClass.name.asc()).all()
    sections = db.query(Section).filter(Section.school_id == school_id, Section.is_active.is_(True)).order_by(Section.name.asc()).all()
    students = db.query(Student).filter(Student.school_id == school_id, Student.is_active.is_(True)).order_by(Student.first_name.asc()).all()
    sessions = db.query(AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).all()

    return FeeMetaResponse(
        categories=[FeeMetaItem(id=item.id, name=item.name, extra=item.code) for item in categories],
        structures=[FeeMetaItem(id=item.id, name=item.name, extra=f"₹{_money(item.amount):,.2f}") for item in structures],
        classes=[FeeMetaItem(id=item.id, name=item.name, extra=item.code) for item in classes],
        sections=[FeeMetaItem(id=item.id, name=item.name, extra=str(item.class_id)) for item in sections],
        students=[FeeMetaItem(id=item.id, name=_full_student_name(item) or item.admission_no, extra=f"{item.admission_no} · Class {item.class_id or '-'}") for item in students],
        academic_sessions=[FeeMetaItem(id=item.id, name=item.name, extra="Active" if item.is_active else None) for item in sessions],
        current_academic_session_id=current_session.id if current_session else None,
    )


@router.get("/dashboard", response_model=FeeDashboardRead)
def fee_dashboard(
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    return _dashboard_summary(db, school_id)


@router.get("/portal", response_model=FeePortalResponse)
def fee_portal(
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT.value, UserRole.PARENT.value)),
    db: Session = Depends(get_db),
):
    student_ids = _authorized_student_ids(db, school_id, current_user)
    if not student_ids:
        return FeePortalResponse(role=current_user.role, summary=_dashboard_summary(db, school_id, []), records=[], payments=[])

    records = (
        _records_query(db, school_id)
        .filter(StudentFeeRecord.student_id.in_(student_ids))
        .order_by(StudentFeeRecord.due_date.asc(), StudentFeeRecord.id.desc())
        .all()
    )
    payments = (
        _payment_query(db, school_id)
        .filter(FeePayment.student_id.in_(student_ids))
        .order_by(FeePayment.payment_date.desc(), FeePayment.id.desc())
        .limit(50)
        .all()
    )
    return FeePortalResponse(
        role=current_user.role,
        summary=_dashboard_summary(db, school_id, student_ids),
        records=[_record_read(record) for record in records],
        payments=[_payment_read(payment) for payment in payments],
    )


@router.get("/categories", response_model=list[FeeCategoryRead])
def list_categories(
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    return [_category_read(item) for item in db.query(FeeCategory).filter(FeeCategory.school_id == school_id).order_by(FeeCategory.id.desc()).all()]


@router.post("/categories", response_model=FeeCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: FeeCategoryCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    category = FeeCategory(school_id=school_id, **payload.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Fee category with this name already exists")
    db.refresh(category)
    return _category_read(category)


@router.put("/categories/{category_id}", response_model=FeeCategoryRead)
def update_category(
    category_id: int,
    payload: FeeCategoryUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    category = _get_or_404(db, FeeCategory, category_id, school_id, "Fee category")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Fee category with this name already exists")
    db.refresh(category)
    return _category_read(category)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(
    category_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    category = _get_or_404(db, FeeCategory, category_id, school_id, "Fee category")
    category.is_active = False
    db.commit()
    return MessageResponse(message="Fee category deactivated")


@router.get("/structures", response_model=list[FeeStructureRead])
def list_structures(
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    structures = db.query(FeeStructure).filter(FeeStructure.school_id == school_id).order_by(FeeStructure.id.desc()).all()
    return [_structure_read(item) for item in structures]


@router.post("/structures", response_model=FeeStructureRead, status_code=status.HTTP_201_CREATED)
def create_structure(
    payload: FeeStructureCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_category(db, school_id, payload.category_id)
    _get_or_404(db, AcademicSession, payload.academic_session_id, school_id, "Academic session")
    structure = FeeStructure(school_id=school_id, **payload.model_dump())
    db.add(structure)
    db.commit()
    db.refresh(structure)
    return _structure_read(structure)


@router.put("/structures/{structure_id}", response_model=FeeStructureRead)
def update_structure(
    structure_id: int,
    payload: FeeStructureUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    structure = _get_or_404(db, FeeStructure, structure_id, school_id, "Fee structure")
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and data["category_id"] is not None:
        _validate_category(db, school_id, data["category_id"])
    if "academic_session_id" in data:
        _get_or_404(db, AcademicSession, data["academic_session_id"], school_id, "Academic session")
    for key, value in data.items():
        setattr(structure, key, value)
    db.commit()
    db.refresh(structure)
    return _structure_read(structure)


@router.delete("/structures/{structure_id}", response_model=MessageResponse)
def delete_structure(
    structure_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    structure = _get_or_404(db, FeeStructure, structure_id, school_id, "Fee structure")
    structure.is_active = False
    db.commit()
    return MessageResponse(message="Fee structure deactivated")


@router.get("/assignments", response_model=list[FeeAssignmentRead])
def list_assignments(
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    assignments = db.query(FeeAssignment).filter(FeeAssignment.school_id == school_id).order_by(FeeAssignment.id.desc()).all()
    return [_assignment_read(db, item) for item in assignments]


@router.post("/assignments", response_model=FeeAssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: FeeAssignmentCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    structure = _validate_structure(db, school_id, payload.fee_structure_id)
    _get_or_404(db, AcademicSession, payload.academic_session_id, school_id, "Academic session")
    _validate_class_scope(db, school_id, payload.class_id, payload.section_id)
    if payload.student_id:
        _validate_student_scope(db, school_id, payload.student_id)

    data = payload.model_dump(exclude={"generate_records"})
    if data.get("academic_session_id") is None:
        data["academic_session_id"] = structure.academic_session_id if structure else None
    assignment = FeeAssignment(school_id=school_id, **data)
    db.add(assignment)
    db.flush()
    if payload.generate_records:
        _generate_records_for_assignment(db, school_id, assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_read(db, assignment)


@router.post("/assignments/{assignment_id}/generate-records", response_model=FeeAssignmentRead)
def generate_assignment_records(
    assignment_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = _get_or_404(db, FeeAssignment, assignment_id, school_id, "Fee assignment")
    _generate_records_for_assignment(db, school_id, assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_read(db, assignment)


@router.put("/assignments/{assignment_id}", response_model=FeeAssignmentRead)
def update_assignment(
    assignment_id: int,
    payload: FeeAssignmentUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = _get_or_404(db, FeeAssignment, assignment_id, school_id, "Fee assignment")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(assignment, key, value)
    db.commit()
    db.refresh(assignment)
    return _assignment_read(db, assignment)


@router.delete("/assignments/{assignment_id}", response_model=MessageResponse)
def delete_assignment(
    assignment_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    assignment = _get_or_404(db, FeeAssignment, assignment_id, school_id, "Fee assignment")
    assignment.is_active = False
    db.commit()
    return MessageResponse(message="Fee assignment deactivated. Existing student fee records are kept for audit.")


@router.get("/records", response_model=list[StudentFeeRecordRead])
def list_records(
    student_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=150, ge=1, le=500),
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    query = _records_query(db, school_id).join(Student, StudentFeeRecord.student_id == Student.id)
    if student_id:
        query = query.filter(StudentFeeRecord.student_id == student_id)
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if section_id:
        query = query.filter(Student.section_id == section_id)
    if status_filter:
        query = query.filter(StudentFeeRecord.status == status_filter.upper())
    records = query.order_by(StudentFeeRecord.due_date.asc(), StudentFeeRecord.id.desc()).limit(limit).all()
    return [_record_read(item) for item in records]


@router.post("/records", response_model=StudentFeeRecordRead, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: StudentFeeRecordCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    _validate_student_scope(db, school_id, payload.student_id)
    _validate_structure(db, school_id, payload.fee_structure_id)
    _get_or_404(db, AcademicSession, payload.academic_session_id, school_id, "Academic session")
    record = StudentFeeRecord(school_id=school_id, paid_amount=0, balance_amount=0, status="PENDING", **payload.model_dump())
    _recalculate_record(record)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_read(record)


@router.put("/records/{record_id}", response_model=StudentFeeRecordRead)
def update_record(
    record_id: int,
    payload: StudentFeeRecordUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    record = _get_or_404(db, StudentFeeRecord, record_id, school_id, "Student fee record")
    data = payload.model_dump(exclude_unset=True)
    requested_status = data.pop("status", None)
    for key, value in data.items():
        setattr(record, key, value)
    if requested_status == "WAIVED":
        record.status = "WAIVED"
    _recalculate_record(record)
    db.commit()
    db.refresh(record)
    return _record_read(record)


@router.delete("/records/{record_id}", response_model=MessageResponse)
def delete_record(
    record_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    record = _get_or_404(db, StudentFeeRecord, record_id, school_id, "Student fee record")
    if record.paid_amount > 0:
        raise HTTPException(status_code=400, detail="Cannot delete a fee record that already has payments")
    db.delete(record)
    db.commit()
    return MessageResponse(message="Student fee record deleted")


@router.get("/payments", response_model=list[FeePaymentRead])
def list_payments(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    student_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    query = _payment_query(db, school_id)
    if from_date:
        query = query.filter(FeePayment.payment_date >= from_date)
    if to_date:
        query = query.filter(FeePayment.payment_date <= to_date)
    if student_id:
        query = query.filter(FeePayment.student_id == student_id)
    payments = query.order_by(FeePayment.payment_date.desc(), FeePayment.id.desc()).limit(limit).all()
    return [_payment_read(item) for item in payments]


@router.post("/payments", response_model=FeeReceiptRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: FeePaymentCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    record = _get_or_404(db, StudentFeeRecord, payload.student_fee_record_id, school_id, "Student fee record")
    if record.status == "WAIVED":
        raise HTTPException(status_code=400, detail="Cannot collect payment for a waived record")
    _recalculate_record(record)
    if payload.amount > record.balance_amount:
        raise HTTPException(status_code=400, detail=f"Payment cannot be greater than pending balance ₹{_money(record.balance_amount):,.2f}")

    payment_date = payload.payment_date or date.today()
    payment = FeePayment(
        school_id=school_id,
        student_fee_record_id=record.id,
        student_id=record.student_id,
        collected_by_user_id=current_user.id,
        receipt_no=_receipt_number(db, school_id, payment_date),
        amount=_money(payload.amount),
        payment_date=payment_date,
        payment_mode=_validate_payment_mode(payload.payment_mode),
        reference_no=payload.reference_no,
        note=payload.note,
    )
    record.paid_amount = _money(record.paid_amount + payment.amount)
    _recalculate_record(record)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    db.refresh(record)

    school = db.get(School, school_id)
    return FeeReceiptRead(payment=_payment_read(payment), record=_record_read(record), school_name=school.name if school else None, school_code=school.school_code if school else None)


@router.get("/receipts/{payment_id}", response_model=FeeReceiptRead)
def get_receipt(
    payment_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = _get_or_404(db, FeePayment, payment_id, school_id, "Fee payment")
    if current_user.role == UserRole.STUDENT.value:
        student_ids = _authorized_student_ids(db, school_id, current_user)
        if payment.student_id not in student_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to view this receipt")
    elif current_user.role == UserRole.PARENT.value:
        student_ids = _authorized_student_ids(db, school_id, current_user)
        if payment.student_id not in student_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to view this receipt")
    elif current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission")

    school = db.get(School, school_id)
    return FeeReceiptRead(payment=_payment_read(payment), record=_record_read(payment.student_fee_record), school_name=school.name if school else None, school_code=school.school_code if school else None)


@router.get("/daily-collection", response_model=DailyCollectionReport)
def daily_collection(
    report_date: date | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    selected_date = report_date or date.today()
    payments = _payment_query(db, school_id).filter(FeePayment.payment_date == selected_date).order_by(FeePayment.id.desc()).all()
    mode_summary: dict[str, float] = {}
    for payment in payments:
        mode_summary[payment.payment_mode] = _money(mode_summary.get(payment.payment_mode, 0) + payment.amount)
    return DailyCollectionReport(
        report_date=selected_date,
        total_collection=_money(sum(payment.amount for payment in payments)),
        total_payments=len(payments),
        payment_mode_summary=mode_summary,
        payments=[_payment_read(payment) for payment in payments],
    )


@router.get("/expenses", response_model=list[FeeExpenseRead])
def list_expenses(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    query = db.query(FeeExpense).filter(FeeExpense.school_id == school_id)
    if from_date:
        query = query.filter(FeeExpense.expense_date >= from_date)
    if to_date:
        query = query.filter(FeeExpense.expense_date <= to_date)
    expenses = query.order_by(FeeExpense.expense_date.desc(), FeeExpense.id.desc()).limit(limit).all()
    return [_expense_read(item) for item in expenses]


@router.post("/expenses", response_model=FeeExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: FeeExpenseCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    expense = FeeExpense(
        school_id=school_id,
        created_by_user_id=current_user.id,
        title=payload.title,
        category=payload.category,
        amount=_money(payload.amount),
        expense_date=payload.expense_date or date.today(),
        payment_mode=_validate_payment_mode(payload.payment_mode),
        vendor_name=payload.vendor_name,
        reference_no=payload.reference_no,
        note=payload.note,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _expense_read(expense)


@router.put("/expenses/{expense_id}", response_model=FeeExpenseRead)
def update_expense(
    expense_id: int,
    payload: FeeExpenseUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    expense = _get_or_404(db, FeeExpense, expense_id, school_id, "Fee expense")
    data = payload.model_dump(exclude_unset=True)
    if "payment_mode" in data and data["payment_mode"] is not None:
        data["payment_mode"] = _validate_payment_mode(data["payment_mode"])
    for key, value in data.items():
        setattr(expense, key, value)
    db.commit()
    db.refresh(expense)
    return _expense_read(expense)


@router.delete("/expenses/{expense_id}", response_model=MessageResponse)
def delete_expense(
    expense_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    expense = _get_or_404(db, FeeExpense, expense_id, school_id, "Fee expense")
    expense.is_active = False
    db.commit()
    return MessageResponse(message="Expense deactivated")
