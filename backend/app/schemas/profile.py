from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    alternate_phone: str | None = Field(default=None, max_length=30)
    occupation: str | None = Field(default=None, max_length=120)
    address: str | None = None
    photo_url: str | None = Field(default=None, max_length=500)


class ProfileResponse(BaseModel):
    account: dict[str, Any]
    school: dict[str, Any] | None = None
    editable_fields: list[str]
    summary: dict[str, Any] = {}
    role_data: dict[str, Any] = {}
