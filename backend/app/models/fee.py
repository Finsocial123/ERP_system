from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FeeCategory(Base):
    __tablename__ = "fee_categories"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_fee_category_school_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    structures = relationship("FeeStructure", back_populates="category")


class FeeStructure(Base):
    __tablename__ = "fee_structures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("fee_categories.id", ondelete="CASCADE"), index=True)
    academic_session_id: Mapped[int | None] = mapped_column(ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("FeeCategory", back_populates="structures")
    academic_session = relationship("AcademicSession")
    assignments = relationship("FeeAssignment", back_populates="fee_structure")
    student_records = relationship("StudentFeeRecord", back_populates="fee_structure")


class FeeAssignment(Base):
    __tablename__ = "fee_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    fee_structure_id: Mapped[int] = mapped_column(ForeignKey("fee_structures.id", ondelete="CASCADE"), index=True)
    academic_session_id: Mapped[int | None] = mapped_column(ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True, index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    section_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)

    assigned_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fee_structure = relationship("FeeStructure", back_populates="assignments")
    academic_session = relationship("AcademicSession")
    school_class = relationship("SchoolClass")
    student = relationship("Student")
    records = relationship("StudentFeeRecord", back_populates="assignment")


class StudentFeeRecord(Base):
    __tablename__ = "student_fee_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    fee_structure_id: Mapped[int | None] = mapped_column(ForeignKey("fee_structures.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_assignment_id: Mapped[int | None] = mapped_column(ForeignKey("fee_assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_session_id: Mapped[int | None] = mapped_column(ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    fine_amount: Mapped[float] = mapped_column(Float, default=0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    balance_amount: Mapped[float] = mapped_column(Float, default=0)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student")
    fee_structure = relationship("FeeStructure", back_populates="student_records")
    assignment = relationship("FeeAssignment", back_populates="records")
    academic_session = relationship("AcademicSession")
    payments = relationship("FeePayment", back_populates="student_fee_record", cascade="all, delete-orphan")


class FeePayment(Base):
    __tablename__ = "fee_payments"
    __table_args__ = (UniqueConstraint("school_id", "receipt_no", name="uq_fee_payment_school_receipt"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    student_fee_record_id: Mapped[int] = mapped_column(ForeignKey("student_fee_records.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    collected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    receipt_no: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    payment_mode: Mapped[str] = mapped_column(String(50), default="CASH")
    reference_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    razorpay_signature: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student_fee_record = relationship("StudentFeeRecord", back_populates="payments")
    student = relationship("Student")
    collected_by = relationship("User")


class FeeExpense(Base):
    __tablename__ = "fee_expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    payment_mode: Mapped[str] = mapped_column(String(50), default="CASH")
    vendor_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("User")
