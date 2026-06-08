from datetime import date

from pydantic import BaseModel, Field


class AcademicSessionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = False


class AcademicSessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


class AcademicSessionRead(BaseModel):
    id: int
    name: str
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = None
    description: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = None
    description: str | None = None
    is_active: bool | None = None


class DepartmentRead(BaseModel):
    id: int
    name: str
    code: str | None = None
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = None
    department_id: int | None = None


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = None
    department_id: int | None = None
    is_active: bool | None = None


class ClassRead(BaseModel):
    id: int
    name: str
    code: str | None = None
    department_id: int | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    class_id: int


class SectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    class_id: int | None = None
    is_active: bool | None = None


class SectionRead(BaseModel):
    id: int
    name: str
    class_id: int
    is_active: bool

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = None
    department_id: int | None = None
    class_id: int | None = None


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = None
    department_id: int | None = None
    class_id: int | None = None
    is_active: bool | None = None


class SubjectRead(BaseModel):
    id: int
    name: str
    code: str | None = None
    department_id: int | None = None
    class_id: int | None = None
    is_active: bool

    model_config = {"from_attributes": True}
