from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class FeeMetaItem(BaseModel):
    id: int
    name: str
    extra: str | None = None


class FeeMetaResponse(BaseModel):
    categories: list[FeeMetaItem]
    structures: list[FeeMetaItem]
    classes: list[FeeMetaItem]
    sections: list[FeeMetaItem]
    students: list[FeeMetaItem]
    academic_sessions: list[FeeMetaItem]
    current_academic_session_id: int | None = None


class FeeCategoryBase(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class FeeCategoryCreate(FeeCategoryBase):
    pass


class FeeCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class FeeCategoryRead(FeeCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime


class FeeStructureCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    category_id: int
    academic_session_id: int | None = None
    amount: float = Field(gt=0)
    due_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class FeeStructureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    category_id: int | None = None
    academic_session_id: int | None = None
    amount: float | None = Field(default=None, gt=0)
    due_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class FeeStructureRead(BaseModel):
    id: int
    name: str
    category_id: int
    category_name: str | None = None
    academic_session_id: int | None = None
    academic_session_name: str | None = None
    amount: float
    due_date: date | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FeeAssignmentCreate(BaseModel):
    fee_structure_id: int
    academic_session_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = Field(default=None, max_length=80)
    student_id: int | None = None
    assigned_amount: float | None = Field(default=None, gt=0)
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)
    generate_records: bool = True

    @model_validator(mode="after")
    def check_assignment_scope(self):
        if not self.class_id and not self.student_id:
            raise ValueError("Assign fee to either a class or a student")
        if self.class_id and self.student_id:
            raise ValueError("Choose class assignment or student assignment, not both")
        if self.section_id and not self.class_id:
            raise ValueError("Section can be selected only with class assignment")
        return self


class FeeAssignmentUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class FeeAssignmentRead(BaseModel):
    id: int
    fee_structure_id: int
    fee_structure_name: str | None = None
    academic_session_id: int | None = None
    academic_session_name: str | None = None
    class_id: int | None = None
    class_name: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    student_id: int | None = None
    student_name: str | None = None
    assigned_amount: float | None = None
    due_date: date | None = None
    note: str | None = None
    is_active: bool
    generated_records_count: int
    generated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StudentFeeRecordCreate(BaseModel):
    student_id: int
    fee_structure_id: int | None = None
    academic_session_id: int | None = None
    title: str = Field(min_length=2, max_length=180)
    amount: float = Field(gt=0)
    discount_amount: float = Field(default=0, ge=0)
    fine_amount: float = Field(default=0, ge=0)
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)


class StudentFeeRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    amount: float | None = Field(default=None, gt=0)
    discount_amount: float | None = Field(default=None, ge=0)
    fine_amount: float | None = Field(default=None, ge=0)
    due_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, max_length=30)


class StudentFeeRecordRead(BaseModel):
    id: int
    student_id: int
    student_name: str | None = None
    admission_no: str | None = None
    roll_number: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    fee_structure_id: int | None = None
    fee_structure_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    fee_type: str = "STRUCTURED"
    fee_assignment_id: int | None = None
    academic_session_id: int | None = None
    academic_session_name: str | None = None
    title: str
    amount: float
    discount_amount: float
    fine_amount: float
    paid_amount: float
    balance_amount: float
    due_date: date | None = None
    status: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class FeePaymentCreate(BaseModel):
    student_fee_record_id: int
    amount: float = Field(gt=0)
    payment_date: date | None = None
    payment_mode: str = Field(default="CASH", max_length=50)
    reference_no: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class FeePaymentRead(BaseModel):
    id: int
    student_fee_record_id: int
    student_id: int
    student_name: str | None = None
    admission_no: str | None = None
    fee_title: str | None = None
    receipt_no: str
    amount: float
    payment_date: date
    payment_mode: str
    reference_no: str | None = None
    note: str | None = None
    collected_by_user_id: int | None = None
    collected_by_name: str | None = None
    created_at: datetime


class FeeReceiptRead(BaseModel):
    payment: FeePaymentRead
    record: StudentFeeRecordRead
    school_name: str | None = None
    school_code: str | None = None


class FeeExpenseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    category: str | None = Field(default=None, max_length=120)
    amount: float = Field(gt=0)
    expense_date: date | None = None
    payment_mode: str = Field(default="CASH", max_length=50)
    vendor_name: str | None = Field(default=None, max_length=180)
    reference_no: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class FeeExpenseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    category: str | None = Field(default=None, max_length=120)
    amount: float | None = Field(default=None, gt=0)
    expense_date: date | None = None
    payment_mode: str | None = Field(default=None, max_length=50)
    vendor_name: str | None = Field(default=None, max_length=180)
    reference_no: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class FeeExpenseRead(BaseModel):
    id: int
    title: str
    category: str | None = None
    amount: float
    expense_date: date
    payment_mode: str
    vendor_name: str | None = None
    reference_no: str | None = None
    note: str | None = None
    is_active: bool
    created_by_user_id: int | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class FeeDashboardRead(BaseModel):
    total_records: int
    pending_records: int
    partial_records: int
    paid_records: int
    overdue_records: int
    total_billable: float
    total_paid: float
    total_pending: float
    today_collection: float
    month_collection: float
    month_expense: float
    net_month_collection: float


class DailyCollectionReport(BaseModel):
    report_date: date
    total_collection: float
    total_payments: int
    payment_mode_summary: dict[str, float]
    payments: list[FeePaymentRead]


class FeePortalResponse(BaseModel):
    role: str
    summary: FeeDashboardRead
    records: list[StudentFeeRecordRead]
    payments: list[FeePaymentRead]


# Razorpay Integration Schemas
class RazorpayOrderCreate(BaseModel):
    student_fee_record_id: int


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key: str
    student_fee_record_id: int
    student_name: str | None
    fee_title: str | None


class RazorpayVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    student_fee_record_id: int

