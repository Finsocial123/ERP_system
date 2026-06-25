from datetime import date, datetime, timedelta
from typing import Any

import razorpay
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from razorpay.errors import SignatureVerificationError
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_query import async_query
from app.core.config import settings
from app.core.database import get_async_db
from app.core.sections import class_section_options, validate_class_section_name
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.dependencies.academic_session import (
    apply_academic_session_filter,
    require_writable_academic_session,
    assert_item_session_is_writable,
    assert_academic_session_is_writable,
    selected_academic_session_id,
)
from app.models.academic import AcademicSession, SchoolClass
from app.models.fee import (
    FeeAssignment,
    FeeCategory,
    FeeExpense,
    FeePayment,
    FeeStructure,
    StudentFeeRecord,
)
from app.models.people import Student
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
    RazorpayOrderCreate,
    RazorpayOrderResponse,
    RazorpayVerify,
    StudentFeeRecordCreate,
    StudentFeeRecordRead,
    StudentFeeRecordUpdate,
)
from app.utils.parent_scope import children_for_parent


router = APIRouter(prefix="/fees", tags=["Phase 6 - Fee Management"], dependencies=[Depends(require_writable_academic_session)])

ADMIN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
)
PAYMENT_MODES = {"CASH", "UPI", "CARD", "BANK_TRANSFER", "CHEQUE", "ONLINE", "OTHER"}
PENDING_STATUSES = {"PENDING", "PARTIAL", "OVERDUE"}


def _money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def _full_student_name(student: Student | None) -> str | None:
    if not student:
        return None
    return f"{student.first_name} {student.last_name or ''}".strip()


def _loaded(obj: Any, relation_name: str):
    """
    Read only already-loaded relationships.

    In async SQLAlchemy, direct lazy access like record.student.name can raise
    MissingGreenlet. Always query with joinedload/selectinload first, then read
    with this helper inside response builders.
    """
    if obj is None:
        return None
    return obj.__dict__.get(relation_name)


def _structure_load_options():
    return (
        joinedload(FeeStructure.category),
        joinedload(FeeStructure.academic_session),
    )


def _assignment_load_options():
    return (
        joinedload(FeeAssignment.fee_structure),
        joinedload(FeeAssignment.academic_session),
        joinedload(FeeAssignment.school_class),
        joinedload(FeeAssignment.student),
    )


def _record_load_options():
    return (
        joinedload(StudentFeeRecord.student).joinedload(Student.school_class),
        joinedload(StudentFeeRecord.fee_structure).joinedload(FeeStructure.category),
        joinedload(StudentFeeRecord.academic_session),
    )


def _payment_load_options():
    return (
        joinedload(FeePayment.student),
        joinedload(FeePayment.student_fee_record)
        .joinedload(StudentFeeRecord.student)
        .joinedload(Student.school_class),
        joinedload(FeePayment.student_fee_record)
        .joinedload(StudentFeeRecord.fee_structure)
        .joinedload(FeeStructure.category),
        joinedload(FeePayment.student_fee_record).joinedload(StudentFeeRecord.academic_session),
        joinedload(FeePayment.collected_by),
    )


def _expense_load_options():
    return (joinedload(FeeExpense.created_by),)


async def _current_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    today = date.today()

    active = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active.is_(True),
    ).order_by(
        AcademicSession.id.desc()
    ).first()

    if active:
        return active

    by_date = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.start_date <= today,
        AcademicSession.end_date >= today,
    ).order_by(
        AcademicSession.id.desc()
    ).first()

    if by_date:
        return by_date

    return await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id
    ).order_by(
        AcademicSession.id.desc()
    ).first()


async def _get_or_404(
    db: AsyncSession,
    model,
    item_id: int | None,
    school_id: int,
    name: str,
):
    if item_id is None:
        return None

    item = await async_query(db, model).filter(
        model.id == item_id,
        model.school_id == school_id,
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail=f"{name} not found for this school")

    return item


async def _student_for_user(
    db: AsyncSession,
    school_id: int,
    user: User,
) -> Student | None:
    student = await async_query(db, Student).filter(
        Student.school_id == school_id,
        Student.user_id == user.id,
    ).first()

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

    return await async_query(db, Student).filter(
        Student.school_id == school_id,
        Student.is_active.is_(True),
        or_(*conditions),
    ).first()


async def _children_for_parent(
    db: AsyncSession,
    school_id: int,
    user: User,
) -> list[Student]:
    return await children_for_parent(db, school_id, user)


def _validate_payment_mode(payment_mode: str) -> str:
    normalized = (payment_mode or "CASH").strip().upper().replace(" ", "_")

    if normalized not in PAYMENT_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment mode. Use one of: {', '.join(sorted(PAYMENT_MODES))}",
        )

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


async def _receipt_number(db: AsyncSession, school_id: int, payment_date: date) -> str:
    date_part = payment_date.strftime("%Y%m%d")
    start = datetime.combine(payment_date, datetime.min.time())
    end = start + timedelta(days=1)

    today_count = await async_query(db, FeePayment).filter(
        FeePayment.school_id == school_id,
        FeePayment.created_at >= start,
        FeePayment.created_at < end,
    ).count()

    return f"FEE-{date_part}-{school_id:03d}-{today_count + 1:04d}"


async def _validate_category(
    db: AsyncSession,
    school_id: int,
    category_id: int,
) -> FeeCategory:
    category = await _get_or_404(db, FeeCategory, category_id, school_id, "Fee category")

    if not category.is_active:
        raise HTTPException(status_code=400, detail="Selected fee category is inactive")

    return category


async def _validate_structure(
    db: AsyncSession,
    school_id: int,
    structure_id: int | None,
) -> FeeStructure | None:
    structure = await _get_or_404(db, FeeStructure, structure_id, school_id, "Fee structure")

    if structure and not structure.is_active:
        raise HTTPException(status_code=400, detail="Selected fee structure is inactive")

    return structure


async def _validate_student_scope(
    db: AsyncSession,
    school_id: int,
    student_id: int,
) -> Student:
    student = await _get_or_404(db, Student, student_id, school_id, "Student")

    if not student.is_active:
        raise HTTPException(status_code=400, detail="Selected student is inactive")

    return student


async def _validate_class_scope(
    db: AsyncSession,
    school_id: int,
    class_id: int | None,
    section_id: int | None,
    section_name: str | None = None,
    academic_session_id: int | None = None,
) -> tuple[SchoolClass | None, str | None]:
    school_class = await _get_or_404(db, SchoolClass, class_id, school_id, "Class")

    if school_class and not school_class.is_active:
        raise HTTPException(status_code=400, detail="Selected class is inactive")

    resolved_section_name = None
    if class_id is not None:
        resolved_section_name = await validate_class_section_name(
            db,
            school_id,
            class_id,
            section_name=section_name,
            section_id=section_id,
            session_id=academic_session_id,
        )

    return school_class, resolved_section_name


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
    category = _loaded(structure, "category")
    academic_session = _loaded(structure, "academic_session")

    return FeeStructureRead(
        id=structure.id,
        name=structure.name,
        category_id=structure.category_id,
        category_name=category.name if category else None,
        academic_session_id=structure.academic_session_id,
        academic_session_name=academic_session.name if academic_session else None,
        amount=_money(structure.amount),
        due_date=structure.due_date,
        description=structure.description,
        is_active=structure.is_active,
        created_at=structure.created_at,
        updated_at=structure.updated_at,
    )


async def _assignment_read(
    db: AsyncSession,
    assignment: FeeAssignment,
    generated_records_count: int | None = None,
) -> FeeAssignmentRead:
    if generated_records_count is None:
        generated_records_count = await async_query(db, StudentFeeRecord).filter(
            StudentFeeRecord.school_id == assignment.school_id,
            StudentFeeRecord.fee_assignment_id == assignment.id,
        ).count()

    fee_structure = _loaded(assignment, "fee_structure")
    academic_session = _loaded(assignment, "academic_session")
    school_class = _loaded(assignment, "school_class")
    student = _loaded(assignment, "student")

    return FeeAssignmentRead(
        id=assignment.id,
        fee_structure_id=assignment.fee_structure_id,
        fee_structure_name=fee_structure.name if fee_structure else None,
        academic_session_id=assignment.academic_session_id,
        academic_session_name=academic_session.name if academic_session else None,
        class_id=assignment.class_id,
        class_name=school_class.name if school_class else None,
        section_id=assignment.section_id,
        section_name=assignment.section_name,
        student_id=assignment.student_id,
        student_name=_full_student_name(student),
        assigned_amount=_money(assignment.assigned_amount) if assignment.assigned_amount is not None else None,
        due_date=assignment.due_date,
        note=assignment.note,
        is_active=assignment.is_active,
        generated_records_count=int(generated_records_count or 0),
        generated_at=assignment.generated_at,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _record_read(record: StudentFeeRecord) -> StudentFeeRecordRead:
    student = _loaded(record, "student")
    fee_structure = _loaded(record, "fee_structure")
    fee_category = _loaded(fee_structure, "category")
    academic_session = _loaded(record, "academic_session")
    school_class = _loaded(student, "school_class")
    return StudentFeeRecordRead(
        id=record.id,
        student_id=record.student_id,
        student_name=_full_student_name(student),
        admission_no=student.admission_no if student else None,
        roll_number=student.roll_number if student else None,
        class_name=school_class.name if school_class else None,
        section_name=student.section_name if student else None,
        fee_structure_id=record.fee_structure_id,
        fee_structure_name=fee_structure.name if fee_structure else None,
        category_id=fee_structure.category_id if fee_structure else None,
        category_name=fee_category.name if fee_category else None,
        fee_type="STRUCTURED" if fee_structure else "MISCELLANEOUS",
        fee_assignment_id=record.fee_assignment_id,
        academic_session_id=record.academic_session_id,
        academic_session_name=academic_session.name if academic_session else None,
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
    student = _loaded(payment, "student")
    record = _loaded(payment, "student_fee_record")
    collected_by = _loaded(payment, "collected_by")

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
        collected_by_name=collected_by.full_name if collected_by else None,
        created_at=payment.created_at,
    )


def _expense_read(expense: FeeExpense) -> FeeExpenseRead:
    created_by = _loaded(expense, "created_by")

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
        created_by_name=created_by.full_name if created_by else None,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


def _records_query(db: AsyncSession, school_id: int):
    return async_query(db, StudentFeeRecord).filter(StudentFeeRecord.school_id == school_id)


def _payment_query(db: AsyncSession, school_id: int):
    return async_query(db, FeePayment).filter(FeePayment.school_id == school_id)


def _apply_record_category_filter(query, category_id: int | None, fee_type: str | None = None):
    if category_id is not None or fee_type:
        query = query.outerjoin(FeeStructure, StudentFeeRecord.fee_structure_id == FeeStructure.id)

    if category_id is not None:
        query = query.filter(FeeStructure.category_id == category_id)

    if fee_type:
        normalized = fee_type.strip().upper()
        if normalized in {"MISC", "MISCELLANEOUS", "MANUAL"}:
            query = query.filter(StudentFeeRecord.fee_structure_id.is_(None))
        elif normalized in {"STRUCTURE", "STRUCTURED", "CATEGORY"}:
            query = query.filter(StudentFeeRecord.fee_structure_id.is_not(None))

    return query


def _apply_payment_session_filter(query, session_id: int | None):
    if session_id is None:
        return query
    return query.join(
        StudentFeeRecord,
        FeePayment.student_fee_record_id == StudentFeeRecord.id,
    ).filter(StudentFeeRecord.academic_session_id == session_id)


def _apply_student_session_filter(query, session_id: int | None):
    if session_id is None:
        return query
    return query.filter(Student.academic_session_id == session_id)


async def _structure_with_relations(
    db: AsyncSession,
    school_id: int,
    structure_id: int,
) -> FeeStructure:
    structure = await async_query(db, FeeStructure).options(
        *_structure_load_options()
    ).filter(
        FeeStructure.school_id == school_id,
        FeeStructure.id == structure_id,
    ).first()

    if not structure:
        raise HTTPException(status_code=404, detail="Fee structure not found for this school")

    return structure


async def _assignment_with_relations(
    db: AsyncSession,
    school_id: int,
    assignment_id: int,
) -> FeeAssignment:
    assignment = await async_query(db, FeeAssignment).options(
        *_assignment_load_options()
    ).filter(
        FeeAssignment.school_id == school_id,
        FeeAssignment.id == assignment_id,
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Fee assignment not found for this school")

    return assignment


async def _record_with_relations(
    db: AsyncSession,
    school_id: int,
    record_id: int,
) -> StudentFeeRecord:
    record = await async_query(db, StudentFeeRecord).options(
        *_record_load_options()
    ).filter(
        StudentFeeRecord.school_id == school_id,
        StudentFeeRecord.id == record_id,
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Student fee record not found for this school")

    return record


async def _payment_with_relations(
    db: AsyncSession,
    school_id: int,
    payment_id: int,
) -> FeePayment:
    payment = await async_query(db, FeePayment).options(
        *_payment_load_options()
    ).filter(
        FeePayment.school_id == school_id,
        FeePayment.id == payment_id,
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Fee payment not found for this school")

    return payment


async def _expense_with_relations(
    db: AsyncSession,
    school_id: int,
    expense_id: int,
) -> FeeExpense:
    expense = await async_query(db, FeeExpense).options(
        *_expense_load_options()
    ).filter(
        FeeExpense.school_id == school_id,
        FeeExpense.id == expense_id,
    ).first()

    if not expense:
        raise HTTPException(status_code=404, detail="Fee expense not found for this school")

    return expense


async def _dashboard_summary(
    db: AsyncSession,
    school_id: int,
    student_ids: list[int] | None = None,
    academic_session_id: int | None = None,
) -> FeeDashboardRead:
    records_query = apply_academic_session_filter(_records_query(db, school_id), StudentFeeRecord, academic_session_id)
    payments_query = _apply_payment_session_filter(_payment_query(db, school_id), academic_session_id)
    expenses_query = async_query(db, FeeExpense).filter(
        FeeExpense.school_id == school_id,
        FeeExpense.is_active.is_(True),
    )

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

    from sqlalchemy import case as _case

    agg = await records_query.with_entities(
        func.count(StudentFeeRecord.id).label("total"),
        func.coalesce(func.sum(_case((StudentFeeRecord.status == "PENDING", 1), else_=0)), 0).label("pending"),
        func.coalesce(func.sum(_case((StudentFeeRecord.status == "PARTIAL", 1), else_=0)), 0).label("partial"),
        func.coalesce(func.sum(_case((StudentFeeRecord.status == "PAID", 1), else_=0)), 0).label("paid"),
        func.coalesce(func.sum(_case((StudentFeeRecord.status == "OVERDUE", 1), else_=0)), 0).label("overdue"),
        func.coalesce(
            func.sum(StudentFeeRecord.amount + StudentFeeRecord.fine_amount - StudentFeeRecord.discount_amount),
            0,
        ).label("billable"),
        func.coalesce(func.sum(StudentFeeRecord.paid_amount), 0).label("paid_amt"),
        func.coalesce(
            func.sum(
                _case(
                    (StudentFeeRecord.status.in_(list(PENDING_STATUSES)), StudentFeeRecord.balance_amount),
                    else_=0,
                )
            ),
            0,
        ).label("pending_amt"),
    ).first()

    today_collection = _money(
        await payments_query.filter(
            FeePayment.payment_date == today
        ).with_entities(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).scalar()
    )

    month_collection = _money(
        await payments_query.filter(
            FeePayment.payment_date >= month_start
        ).with_entities(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).scalar()
    )

    month_expense = _money(
        await expenses_query.filter(
            FeeExpense.expense_date >= month_start
        ).with_entities(
            func.coalesce(func.sum(FeeExpense.amount), 0)
        ).scalar()
    )

    return FeeDashboardRead(
        total_records=int(agg.total or 0),
        pending_records=int(agg.pending or 0),
        partial_records=int(agg.partial or 0),
        paid_records=int(agg.paid or 0),
        overdue_records=int(agg.overdue or 0),
        total_billable=_money(agg.billable),
        total_paid=_money(agg.paid_amt),
        total_pending=_money(agg.pending_amt),
        today_collection=today_collection,
        month_collection=month_collection,
        month_expense=month_expense,
        net_month_collection=_money(month_collection - month_expense),
    )


async def _students_for_assignment(
    db: AsyncSession,
    school_id: int,
    assignment: FeeAssignment,
) -> list[Student]:
    if assignment.student_id:
        student = await _validate_student_scope(db, school_id, assignment.student_id)
        return [student]

    if not assignment.class_id:
        return []

    query = async_query(db, Student).filter(
        Student.school_id == school_id,
        Student.class_id == assignment.class_id,
        Student.is_active.is_(True),
    )

    if assignment.section_name:
        query = query.filter(Student.section_name == assignment.section_name)
    elif assignment.section_id:
        query = query.filter(Student.section_id == assignment.section_id)

    return await query.order_by(
        Student.roll_number.asc(),
        Student.first_name.asc(),
    ).all()


async def _generate_records_for_assignment(
    db: AsyncSession,
    school_id: int,
    assignment: FeeAssignment,
) -> int:
    structure = _loaded(assignment, "fee_structure")

    if not structure and assignment.fee_structure_id:
        structure = await async_query(db, FeeStructure).filter(
            FeeStructure.school_id == school_id,
            FeeStructure.id == assignment.fee_structure_id,
        ).first()

    if not structure:
        return 0

    students = await _students_for_assignment(db, school_id, assignment)
    amount = assignment.assigned_amount if assignment.assigned_amount is not None else structure.amount
    due_date = assignment.due_date or structure.due_date
    generated = 0

    for student in students:
        existing = await async_query(db, StudentFeeRecord).filter(
            StudentFeeRecord.school_id == school_id,
            StudentFeeRecord.student_id == student.id,
            StudentFeeRecord.fee_assignment_id == assignment.id,
        ).first()

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


async def _authorized_student_ids(
    db: AsyncSession,
    school_id: int,
    current_user: User,
) -> list[int]:
    if current_user.role == UserRole.STUDENT.value:
        student = await _student_for_user(db, school_id, current_user)
        return [student.id] if student else []

    if current_user.role == UserRole.PARENT.value:
        return [student.id for student in await _children_for_parent(db, school_id, current_user)]

    return []


@router.get("/meta", response_model=FeeMetaResponse)
async def fee_meta(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    current_session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )

    categories = await async_query(db, FeeCategory).filter(
        FeeCategory.school_id == school_id,
        FeeCategory.is_active.is_(True),
    ).order_by(
        FeeCategory.name.asc()
    ).all()

    structures_query = apply_academic_session_filter(
        async_query(db, FeeStructure).options(*_structure_load_options()).filter(
            FeeStructure.school_id == school_id,
            FeeStructure.is_active.is_(True),
        ),
        FeeStructure,
        current_session_id,
    )
    structures = await structures_query.order_by(FeeStructure.name.asc()).all()

    classes_query = apply_academic_session_filter(
        async_query(db, SchoolClass).filter(
            SchoolClass.school_id == school_id,
            SchoolClass.is_active.is_(True),
        ),
        SchoolClass,
        current_session_id,
    )
    classes = await classes_query.order_by(SchoolClass.name.asc()).all()

    students_query = apply_academic_session_filter(
        async_query(db, Student).filter(
            Student.school_id == school_id,
            Student.is_active.is_(True),
        ),
        Student,
        current_session_id,
    )
    students = await students_query.order_by(Student.first_name.asc()).all()

    sessions = await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id
    ).order_by(
        AcademicSession.id.desc()
    ).all()

    return FeeMetaResponse(
        categories=[FeeMetaItem(id=item.id, name=item.name, extra=item.code) for item in categories],
        structures=[
            FeeMetaItem(id=item.id, name=item.name, extra=f"₹{_money(item.amount):,.2f}")
            for item in structures
        ],
        classes=[FeeMetaItem(id=item.id, name=item.name, extra=item.code) for item in classes],
        sections=[FeeMetaItem(id=item.id, name=item.name, extra=str(item.extra)) for item in await class_section_options(db, school_id, session_id=current_session_id)],
        students=[
            FeeMetaItem(
                id=item.id,
                name=_full_student_name(item) or item.admission_no,
                extra=f"{item.admission_no} · Class {item.class_id or '-'}",
            )
            for item in students
        ],
        academic_sessions=[
            FeeMetaItem(id=item.id, name=item.name, extra="Active" if item.is_active else None)
            for item in sessions
        ],
        current_academic_session_id=current_session_id,
    )


@router.get("/dashboard", response_model=FeeDashboardRead)
async def fee_dashboard(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    return await _dashboard_summary(db, school_id, academic_session_id=session_id)


@router.get("/portal", response_model=FeePortalResponse)
async def fee_portal(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(UserRole.STUDENT.value, UserRole.PARENT.value)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    student_ids = await _authorized_student_ids(db, school_id, current_user)

    if not student_ids:
        return FeePortalResponse(
            role=current_user.role,
            summary=await _dashboard_summary(db, school_id, [], academic_session_id=session_id),
            records=[],
            payments=[],
        )

    records_query = apply_academic_session_filter(
        _records_query(db, school_id),
        StudentFeeRecord,
        session_id,
    ).options(*_record_load_options()).filter(
        StudentFeeRecord.student_id.in_(student_ids)
    )

    records = await records_query.order_by(
        StudentFeeRecord.due_date.asc(),
        StudentFeeRecord.id.desc(),
    ).all()

    payments_query = _apply_payment_session_filter(
        _payment_query(db, school_id),
        session_id,
    ).options(*_payment_load_options()).filter(
        FeePayment.student_id.in_(student_ids)
    )

    payments = await payments_query.order_by(
        FeePayment.payment_date.desc(),
        FeePayment.id.desc(),
    ).limit(50).all()

    return FeePortalResponse(
        role=current_user.role,
        summary=await _dashboard_summary(db, school_id, student_ids, academic_session_id=session_id),
        records=[_record_read(record) for record in records],
        payments=[_payment_read(payment) for payment in payments],
    )


@router.get("/categories", response_model=list[FeeCategoryRead])
async def list_categories(
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    categories = await async_query(db, FeeCategory).filter(
        FeeCategory.school_id == school_id
    ).order_by(
        FeeCategory.id.desc()
    ).all()

    return [_category_read(item) for item in categories]


@router.post("/categories", response_model=FeeCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: FeeCategoryCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    category = FeeCategory(school_id=school_id, **payload.model_dump())
    db.add(category)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Fee category with this name already exists")

    await db.refresh(category)
    return _category_read(category)


@router.put("/categories/{category_id}", response_model=FeeCategoryRead)
async def update_category(
    category_id: int,
    payload: FeeCategoryUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    category = await _get_or_404(db, FeeCategory, category_id, school_id, "Fee category")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, key, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Fee category with this name already exists")

    await db.refresh(category)
    return _category_read(category)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    category = await _get_or_404(db, FeeCategory, category_id, school_id, "Fee category")
    category.is_active = False
    await db.commit()
    return MessageResponse(message="Fee category deactivated")


@router.get("/structures", response_model=list[FeeStructureRead])
async def list_structures(
    request: Request,
    category_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    query = apply_academic_session_filter(
        async_query(db, FeeStructure).options(*_structure_load_options()).filter(
            FeeStructure.school_id == school_id
        ),
        FeeStructure,
        session_id,
    )

    if category_id:
        query = query.filter(FeeStructure.category_id == category_id)

    structures = await query.order_by(
        FeeStructure.id.desc()
    ).all()

    return [_structure_read(item) for item in structures]


@router.post("/structures", response_model=FeeStructureRead, status_code=status.HTTP_201_CREATED)
async def create_structure(
    payload: FeeStructureCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    await _validate_category(db, school_id, payload.category_id)
    await assert_academic_session_is_writable(db, school_id, payload.academic_session_id)

    structure = FeeStructure(school_id=school_id, **payload.model_dump())
    db.add(structure)
    await db.commit()
    await db.refresh(structure)

    structure = await _structure_with_relations(db, school_id, structure.id)
    return _structure_read(structure)


@router.put("/structures/{structure_id}", response_model=FeeStructureRead)
async def update_structure(
    structure_id: int,
    payload: FeeStructureUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    structure = await _get_or_404(db, FeeStructure, structure_id, school_id, "Fee structure")
    await assert_item_session_is_writable(db, school_id, structure)
    data = payload.model_dump(exclude_unset=True)

    if "category_id" in data and data["category_id"] is not None:
        await _validate_category(db, school_id, data["category_id"])

    if "academic_session_id" in data:
        await assert_academic_session_is_writable(db, school_id, data["academic_session_id"])

    for key, value in data.items():
        setattr(structure, key, value)

    await db.commit()
    await db.refresh(structure)

    structure = await _structure_with_relations(db, school_id, structure.id)
    return _structure_read(structure)


@router.delete("/structures/{structure_id}", response_model=MessageResponse)
async def delete_structure(
    structure_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    structure = await _get_or_404(db, FeeStructure, structure_id, school_id, "Fee structure")
    await assert_item_session_is_writable(db, school_id, structure)
    structure.is_active = False
    await db.commit()
    return MessageResponse(message="Fee structure deactivated")


@router.get("/assignments", response_model=list[FeeAssignmentRead])
async def list_assignments(
    request: Request,
    class_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    query = apply_academic_session_filter(
        async_query(db, FeeAssignment).options(*_assignment_load_options()).filter(
            FeeAssignment.school_id == school_id
        ),
        FeeAssignment,
        session_id,
    )

    if class_id:
        query = query.filter(FeeAssignment.class_id == class_id)

    if category_id:
        query = query.join(FeeStructure, FeeAssignment.fee_structure_id == FeeStructure.id).filter(
            FeeStructure.category_id == category_id
        )

    assignments = await query.order_by(
        FeeAssignment.id.desc()
    ).all()

    assignment_ids = [assignment.id for assignment in assignments]
    record_counts: dict[int, int] = {}

    if assignment_ids:
        rows = await async_query(
            db,
            StudentFeeRecord.fee_assignment_id,
            func.count(StudentFeeRecord.id),
        ).filter(
            StudentFeeRecord.school_id == school_id,
            StudentFeeRecord.fee_assignment_id.in_(assignment_ids),
        ).group_by(
            StudentFeeRecord.fee_assignment_id
        ).all()
        record_counts = {int(assignment_id): int(count or 0) for assignment_id, count in rows}

    return [
        await _assignment_read(
            db,
            assignment,
            generated_records_count=record_counts.get(assignment.id, 0),
        )
        for assignment in assignments
    ]


@router.post("/assignments", response_model=FeeAssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: FeeAssignmentCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    structure = await _validate_structure(db, school_id, payload.fee_structure_id)
    await assert_academic_session_is_writable(db, school_id, payload.academic_session_id)
    _, resolved_section_name = await _validate_class_scope(db, school_id, payload.class_id, payload.section_id, payload.section_name, payload.academic_session_id)

    if payload.student_id:
        await _validate_student_scope(db, school_id, payload.student_id)

    data = payload.model_dump(exclude={"generate_records"})
    data["section_id"] = None
    data["section_name"] = resolved_section_name

    if data.get("academic_session_id") is None:
        data["academic_session_id"] = structure.academic_session_id if structure else None

    assignment = FeeAssignment(school_id=school_id, **data)
    db.add(assignment)
    await db.flush()

    if payload.generate_records:
        await _generate_records_for_assignment(db, school_id, assignment)

    await db.commit()
    await db.refresh(assignment)

    assignment = await _assignment_with_relations(db, school_id, assignment.id)
    return await _assignment_read(db, assignment)


@router.post("/assignments/{assignment_id}/generate-records", response_model=FeeAssignmentRead)
async def generate_assignment_records(
    assignment_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    assignment = await _assignment_with_relations(db, school_id, assignment_id)
    await assert_item_session_is_writable(db, school_id, assignment)
    await _generate_records_for_assignment(db, school_id, assignment)
    await db.commit()
    await db.refresh(assignment)

    assignment = await _assignment_with_relations(db, school_id, assignment.id)
    return await _assignment_read(db, assignment)


@router.put("/assignments/{assignment_id}", response_model=FeeAssignmentRead)
async def update_assignment(
    assignment_id: int,
    payload: FeeAssignmentUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    assignment = await _get_or_404(db, FeeAssignment, assignment_id, school_id, "Fee assignment")
    await assert_item_session_is_writable(db, school_id, assignment)

    data = payload.model_dump(exclude_unset=True)
    if any(key in data for key in ("class_id", "section_id", "section_name", "academic_session_id")):
        class_id = data.get("class_id", assignment.class_id)
        section_id = data.get("section_id", assignment.section_id)
        section_name = data.get("section_name", assignment.section_name)
        academic_session_id = data.get("academic_session_id", assignment.academic_session_id)
        _, resolved_section_name = await _validate_class_scope(db, school_id, class_id, section_id, section_name, academic_session_id)
        data["section_id"] = None
        data["section_name"] = resolved_section_name
    for key, value in data.items():
        setattr(assignment, key, value)

    await db.commit()
    await db.refresh(assignment)

    assignment = await _assignment_with_relations(db, school_id, assignment.id)
    return await _assignment_read(db, assignment)


@router.delete("/assignments/{assignment_id}", response_model=MessageResponse)
async def delete_assignment(
    assignment_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    assignment = await _get_or_404(db, FeeAssignment, assignment_id, school_id, "Fee assignment")
    await assert_item_session_is_writable(db, school_id, assignment)
    assignment.is_active = False
    await db.commit()
    return MessageResponse(message="Fee assignment deactivated. Existing student fee records are kept for audit.")


@router.get("/records", response_model=list[StudentFeeRecordRead])
async def list_records(
    request: Request,
    student_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    fee_structure_id: int | None = Query(default=None),
    fee_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=150, ge=1, le=500),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    query = apply_academic_session_filter(
        _records_query(db, school_id),
        StudentFeeRecord,
        session_id,
    ).join(Student, StudentFeeRecord.student_id == Student.id)

    if student_id:
        query = query.filter(StudentFeeRecord.student_id == student_id)

    if class_id:
        query = query.filter(Student.class_id == class_id)

    if section_id and class_id:
        section_name = await validate_class_section_name(db, school_id, class_id, section_id=section_id, session_id=session_id)
        query = query.filter(Student.section_name == section_name)
    elif section_id:
        query = query.filter(Student.section_id == section_id)

    if fee_structure_id:
        query = query.filter(StudentFeeRecord.fee_structure_id == fee_structure_id)

    query = _apply_record_category_filter(query, category_id, fee_type)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                StudentFeeRecord.title.ilike(pattern),
                Student.admission_no.ilike(pattern),
                Student.first_name.ilike(pattern),
                Student.last_name.ilike(pattern),
            )
        )

    if status_filter:
        query = query.filter(StudentFeeRecord.status == status_filter.upper())

    records = await query.options(
        *_record_load_options()
    ).order_by(
        Student.class_id.asc(),
        Student.roll_number.asc(),
        StudentFeeRecord.due_date.asc(),
        StudentFeeRecord.id.desc(),
    ).limit(limit).all()

    return [_record_read(item) for item in records]


@router.post("/records", response_model=StudentFeeRecordRead, status_code=status.HTTP_201_CREATED)
async def create_record(
    payload: StudentFeeRecordCreate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    await _validate_student_scope(db, school_id, payload.student_id)
    await _validate_structure(db, school_id, payload.fee_structure_id)
    await assert_academic_session_is_writable(db, school_id, payload.academic_session_id)

    record = StudentFeeRecord(
        school_id=school_id,
        paid_amount=0,
        balance_amount=0,
        status="PENDING",
        **payload.model_dump(),
    )

    _recalculate_record(record)
    db.add(record)
    await db.commit()
    await db.refresh(record)

    record = await _record_with_relations(db, school_id, record.id)
    return _record_read(record)


@router.put("/records/{record_id}", response_model=StudentFeeRecordRead)
async def update_record(
    record_id: int,
    payload: StudentFeeRecordUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    record = await _get_or_404(db, StudentFeeRecord, record_id, school_id, "Student fee record")
    await assert_item_session_is_writable(db, school_id, record)
    data = payload.model_dump(exclude_unset=True)
    requested_status = data.pop("status", None)

    for key, value in data.items():
        setattr(record, key, value)

    if requested_status == "WAIVED":
        record.status = "WAIVED"

    _recalculate_record(record)
    await db.commit()
    await db.refresh(record)

    record = await _record_with_relations(db, school_id, record.id)
    return _record_read(record)


@router.delete("/records/{record_id}", response_model=MessageResponse)
async def delete_record(
    record_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    record = await _get_or_404(db, StudentFeeRecord, record_id, school_id, "Student fee record")
    await assert_item_session_is_writable(db, school_id, record)

    if record.paid_amount > 0:
        raise HTTPException(status_code=400, detail="Cannot delete a fee record that already has payments")

    await db.delete(record)
    await db.commit()
    return MessageResponse(message="Student fee record deleted")


@router.get("/payments", response_model=list[FeePaymentRead])
async def list_payments(
    request: Request,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    student_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    query = _apply_payment_session_filter(_payment_query(db, school_id), session_id)

    if from_date:
        query = query.filter(FeePayment.payment_date >= from_date)

    if to_date:
        query = query.filter(FeePayment.payment_date <= to_date)

    if student_id:
        query = query.filter(FeePayment.student_id == student_id)

    payments = await query.options(
        *_payment_load_options()
    ).order_by(
        FeePayment.payment_date.desc(),
        FeePayment.id.desc(),
    ).limit(limit).all()

    return [_payment_read(item) for item in payments]


@router.post("/payments", response_model=FeeReceiptRead, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: FeePaymentCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    record = await _record_with_relations(db, school_id, payload.student_fee_record_id)
    await assert_item_session_is_writable(db, school_id, record)

    if record.status == "WAIVED":
        raise HTTPException(status_code=400, detail="Cannot collect payment for a waived record")

    _recalculate_record(record)

    if payload.amount > record.balance_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Payment cannot be greater than pending balance ₹{_money(record.balance_amount):,.2f}",
        )

    payment_date = payload.payment_date or date.today()

    payment = FeePayment(
        school_id=school_id,
        student_fee_record_id=record.id,
        student_id=record.student_id,
        collected_by_user_id=current_user.id,
        receipt_no=await _receipt_number(db, school_id, payment_date),
        amount=_money(payload.amount),
        payment_date=payment_date,
        payment_mode=_validate_payment_mode(payload.payment_mode),
        reference_no=payload.reference_no,
        note=payload.note,
    )

    record.paid_amount = _money(record.paid_amount + payment.amount)
    _recalculate_record(record)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    payment = await _payment_with_relations(db, school_id, payment.id)
    record = _loaded(payment, "student_fee_record")

    if not record:
        raise HTTPException(status_code=500, detail="Fee record could not be loaded after payment")

    school = await db.get(School, school_id)

    return FeeReceiptRead(
        payment=_payment_read(payment),
        record=_record_read(record),
        school_name=school.name if school else None,
        school_code=school.school_code if school else None,
    )


@router.get("/receipts/{payment_id}", response_model=FeeReceiptRead)
async def get_receipt(
    payment_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    payment = await _payment_with_relations(db, school_id, payment_id)

    if current_user.role == UserRole.STUDENT.value:
        student_ids = await _authorized_student_ids(db, school_id, current_user)
        if payment.student_id not in student_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to view this receipt")

    elif current_user.role == UserRole.PARENT.value:
        student_ids = await _authorized_student_ids(db, school_id, current_user)
        if payment.student_id not in student_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to view this receipt")

    elif current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission")

    record = _loaded(payment, "student_fee_record")
    if not record:
        raise HTTPException(status_code=404, detail="Fee record not found for this payment")

    school = await db.get(School, school_id)

    return FeeReceiptRead(
        payment=_payment_read(payment),
        record=_record_read(record),
        school_name=school.name if school else None,
        school_code=school.school_code if school else None,
    )


@router.get("/daily-collection", response_model=DailyCollectionReport)
async def daily_collection(
    request: Request,
    report_date: date | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
    )
    selected_date = report_date or date.today()

    payments = await _apply_payment_session_filter(
        _payment_query(db, school_id),
        session_id,
    ).options(
        *_payment_load_options()
    ).filter(
        FeePayment.payment_date == selected_date
    ).order_by(
        FeePayment.id.desc()
    ).all()

    mode_summary: dict[str, float] = {}

    for payment in payments:
        mode_summary[payment.payment_mode] = _money(
            mode_summary.get(payment.payment_mode, 0) + payment.amount
        )

    return DailyCollectionReport(
        report_date=selected_date,
        total_collection=_money(sum(payment.amount for payment in payments)),
        total_payments=len(payments),
        payment_mode_summary=mode_summary,
        payments=[_payment_read(payment) for payment in payments],
    )


@router.get("/expenses", response_model=list[FeeExpenseRead])
async def list_expenses(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    query = async_query(db, FeeExpense).filter(FeeExpense.school_id == school_id)

    if from_date:
        query = query.filter(FeeExpense.expense_date >= from_date)

    if to_date:
        query = query.filter(FeeExpense.expense_date <= to_date)

    expenses = await query.options(
        *_expense_load_options()
    ).order_by(
        FeeExpense.expense_date.desc(),
        FeeExpense.id.desc(),
    ).limit(limit).all()

    return [_expense_read(item) for item in expenses]


@router.post("/expenses", response_model=FeeExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: FeeExpenseCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
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
    await db.commit()
    await db.refresh(expense)

    expense = await _expense_with_relations(db, school_id, expense.id)
    return _expense_read(expense)


@router.put("/expenses/{expense_id}", response_model=FeeExpenseRead)
async def update_expense(
    expense_id: int,
    payload: FeeExpenseUpdate,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    expense = await _get_or_404(db, FeeExpense, expense_id, school_id, "Fee expense")
    data = payload.model_dump(exclude_unset=True)

    if "payment_mode" in data and data["payment_mode"] is not None:
        data["payment_mode"] = _validate_payment_mode(data["payment_mode"])

    for key, value in data.items():
        setattr(expense, key, value)

    await db.commit()
    await db.refresh(expense)

    expense = await _expense_with_relations(db, school_id, expense.id)
    return _expense_read(expense)


@router.delete("/expenses/{expense_id}", response_model=MessageResponse)
async def delete_expense(
    expense_id: int,
    school_id: int = Depends(current_school_id),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    expense = await _get_or_404(db, FeeExpense, expense_id, school_id, "Fee expense")
    expense.is_active = False
    await db.commit()
    return MessageResponse(message="Expense deactivated")


@router.post("/razorpay/create-order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(
    payload: RazorpayOrderCreate,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    record = await _record_with_relations(db, school_id, payload.student_fee_record_id)
    await assert_item_session_is_writable(db, school_id, record)

    if current_user.role in (UserRole.STUDENT.value, UserRole.PARENT.value):
        authorized_ids = await _authorized_student_ids(db, school_id, current_user)
        if record.student_id not in authorized_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to pay for this fee record")

    if record.status == "WAIVED":
        raise HTTPException(status_code=400, detail="Cannot collect payment for a waived record")

    _recalculate_record(record)
    amount_paise = int(record.balance_amount * 100)

    if amount_paise < 100:
        raise HTTPException(status_code=400, detail="Balance amount is too low for online payment (minimum ₹1)")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"fee_{record.id}_{school_id}",
            "notes": {
                "student_fee_record_id": str(record.id),
                "school_id": str(school_id),
            },
        }
    )

    student = _loaded(record, "student")

    return RazorpayOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        key=settings.RAZORPAY_KEY_ID,
        student_fee_record_id=record.id,
        student_name=_full_student_name(student),
        fee_title=record.title,
    )


@router.post("/razorpay/verify-payment", response_model=FeeReceiptRead)
async def verify_razorpay_payment(
    payload: RazorpayVerify,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": payload.razorpay_order_id,
                "razorpay_payment_id": payload.razorpay_payment_id,
                "razorpay_signature": payload.razorpay_signature,
            }
        )
    except SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    existing_payment = await async_query(db, FeePayment).options(
        *_payment_load_options()
    ).filter(
        FeePayment.school_id == school_id,
        FeePayment.razorpay_payment_id == payload.razorpay_payment_id,
    ).first()

    if existing_payment:
        record = _loaded(existing_payment, "student_fee_record")
        if not record:
            raise HTTPException(status_code=404, detail="Fee record not found for this payment")

        school = await db.get(School, school_id)
        return FeeReceiptRead(
            payment=_payment_read(existing_payment),
            record=_record_read(record),
            school_name=school.name if school else None,
            school_code=school.school_code if school else None,
        )

    record = await _record_with_relations(db, school_id, payload.student_fee_record_id)
    await assert_item_session_is_writable(db, school_id, record)

    if current_user.role in (UserRole.STUDENT.value, UserRole.PARENT.value):
        authorized_ids = await _authorized_student_ids(db, school_id, current_user)
        if record.student_id not in authorized_ids:
            raise HTTPException(status_code=403, detail="You do not have permission to verify this payment")

    if record.status == "WAIVED":
        raise HTTPException(status_code=400, detail="Cannot collect payment for a waived record")

    _recalculate_record(record)

    payment_details = client.payment.fetch(payload.razorpay_payment_id)
    amount = _money(payment_details["amount"] / 100)

    if amount > record.balance_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Payment cannot exceed pending balance ₹{_money(record.balance_amount):,.2f}",
        )

    payment_date = date.today()

    payment = FeePayment(
        school_id=school_id,
        student_fee_record_id=record.id,
        student_id=record.student_id,
        collected_by_user_id=current_user.id,
        receipt_no=await _receipt_number(db, school_id, payment_date),
        amount=amount,
        payment_date=payment_date,
        payment_mode="ONLINE",
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )

    record.paid_amount = _money(record.paid_amount + payment.amount)
    _recalculate_record(record)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    payment = await _payment_with_relations(db, school_id, payment.id)
    record = _loaded(payment, "student_fee_record")

    if not record:
        raise HTTPException(status_code=500, detail="Fee record could not be loaded after payment")

    school = await db.get(School, school_id)

    return FeeReceiptRead(
        payment=_payment_read(payment),
        record=_record_read(record),
        school_name=school.name if school else None,
        school_code=school.school_code if school else None,
    )
