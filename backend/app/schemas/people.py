from datetime import date

from pydantic import BaseModel, EmailStr, Field


class ParentGuardianBase(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    relation: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    alternate_phone: str | None = Field(default=None, max_length=30)
    occupation: str | None = Field(default=None, max_length=120)
    address: str | None = None


class ParentGuardianCreate(ParentGuardianBase):
    full_name: str = Field(min_length=2, max_length=150)


class ParentGuardianUpdate(ParentGuardianBase):
    is_active: bool | None = None


class ParentGuardianRead(ParentGuardianBase):
    id: int
    full_name: str
    user_id: int | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class ParentLoginCreate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=72)


class StudentCreate(BaseModel):
    academic_session_id: int | None = None
    create_login: bool = False
    password: str | None = Field(default=None, min_length=6, max_length=72)
    create_parent_login: bool = False
    parent_password: str | None = Field(default=None, min_length=6, max_length=72)
    admission_no: str = Field(min_length=1, max_length=80)
    roll_number: str | None = Field(default=None, max_length=80)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    blood_group: str | None = Field(default=None, max_length=20)
    photo_url: str | None = Field(default=None, max_length=500)
    address: str | None = None
    admission_date: date | None = None
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = Field(default=None, max_length=80)
    guardian: ParentGuardianCreate | None = None


class StudentUpdate(BaseModel):
    academic_session_id: int | None = None
    create_parent_login: bool = False
    parent_password: str | None = Field(default=None, min_length=6, max_length=72)
    admission_no: str | None = Field(default=None, min_length=1, max_length=80)
    roll_number: str | None = Field(default=None, max_length=80)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    date_of_birth: date | None = None
    blood_group: str | None = Field(default=None, max_length=20)
    photo_url: str | None = Field(default=None, max_length=500)
    address: str | None = None
    admission_date: date | None = None
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = Field(default=None, max_length=80)
    status: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None
    guardian: ParentGuardianUpdate | None = None


class StudentRead(BaseModel):
    id: int
    academic_session_id: int | None = None
    admission_no: str
    roll_number: str | None = None
    first_name: str
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    blood_group: str | None = None
    photo_url: str | None = None
    address: str | None = None
    admission_date: date | None = None
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = None
    guardian: ParentGuardianRead | None = None
    status: str
    is_active: bool
    user_id: int | None = None
    temporary_password: str | None = None
    parent_temporary_password: str | None = None
    parent_login_id: str | None = None

    model_config = {"from_attributes": True}


class TeacherCreate(BaseModel):
    academic_session_id: int | None = None
    employee_id: str = Field(min_length=1, max_length=80)
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    department_id: int | None = None
    qualification: str | None = Field(default=None, max_length=150)
    specialization: str | None = Field(default=None, max_length=150)
    joining_date: date | None = None
    photo_url: str | None = Field(default=None, max_length=500)
    address: str | None = None
    create_login: bool = False
    password: str | None = Field(default=None, min_length=6, max_length=72)


class TeacherUpdate(BaseModel):
    academic_session_id: int | None = None
    employee_id: str | None = Field(default=None, min_length=1, max_length=80)
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    department_id: int | None = None
    qualification: str | None = Field(default=None, max_length=150)
    specialization: str | None = Field(default=None, max_length=150)
    joining_date: date | None = None
    photo_url: str | None = Field(default=None, max_length=500)
    address: str | None = None
    status: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class TeacherRead(BaseModel):
    id: int
    academic_session_id: int | None = None
    employee_id: str
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    gender: str | None = None
    department_id: int | None = None
    qualification: str | None = None
    specialization: str | None = None
    joining_date: date | None = None
    photo_url: str | None = None
    address: str | None = None
    status: str
    is_active: bool
    user_id: int | None = None
    temporary_password: str | None = None

    model_config = {"from_attributes": True}


class TeacherSubjectCreate(BaseModel):
    academic_session_id: int | None = None
    subject_id: int
    class_id: int
    section_id: int | None = None
    section_name: str | None = Field(default=None, max_length=80)


class TeacherSubjectRead(BaseModel):
    id: int
    academic_session_id: int | None = None
    teacher_id: int
    subject_id: int
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = None

    model_config = {"from_attributes": True}


class ClassTeacherCreate(BaseModel):
    teacher_id: int
    class_id: int
    section_id: int | None = None
    section_name: str | None = Field(default=None, max_length=80)
    academic_session_id: int | None = None


class ClassTeacherRead(BaseModel):
    id: int
    teacher_id: int
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    academic_session_id: int | None = None

    model_config = {"from_attributes": True}
