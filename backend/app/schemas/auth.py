from pydantic import BaseModel, EmailStr, Field, field_validator


class SchoolRegisterRequest(BaseModel):
    school_name: str = Field(min_length=2, max_length=200)
    school_code: str | None = Field(default=None, min_length=3, max_length=40)
    institution_type: str = "school"
    school_email: EmailStr | None = None
    school_phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = "India"

    owner_name: str = Field(min_length=2, max_length=150)
    owner_email: EmailStr
    owner_phone: str | None = None
    owner_password: str = Field(min_length=6, max_length=72)

    @field_validator("owner_password")
    @classmethod
    def validate_owner_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or less")
        return value


class SchoolRegistrationOtpResponse(BaseModel):
    message: str
    owner_email: EmailStr
    expires_in_minutes: int
    debug_otp: str | None = None


class SchoolRegistrationVerifyRequest(BaseModel):
    owner_email: EmailStr
    otp: str = Field(min_length=4, max_length=10)


class LoginRequest(BaseModel):
    school_code: str = Field(min_length=2, max_length=40)
    login_id: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str
    selected_role: str | None = Field(default=None, max_length=30)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or less")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=6, max_length=72)


class ForgotPasswordRequest(BaseModel):
    school_code: str = Field(min_length=2, max_length=40)
    login_id: str = Field(min_length=1, max_length=255)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None
    reset_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=6, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or less")
        return value


class SchoolPublic(BaseModel):
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

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    id: int
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    login_id: str | None = None
    role: str
    school_id: int | None = None
    must_change_password: bool = False
    photo_url: str | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    refresh_expires_in: int | None = None
    user: UserPublic
    school: SchoolPublic | None = None


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
