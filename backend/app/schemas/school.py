from pydantic import BaseModel, EmailStr, Field


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    school_code: str | None = Field(default=None, min_length=3, max_length=40)
    institution_type: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    logo_url: str | None = Field(default=None, max_length=500)


class SchoolRead(BaseModel):
    id: int
    name: str
    slug: str
    school_code: str
    institution_type: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    logo_url: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
