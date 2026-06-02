import re

from pydantic import BaseModel, EmailStr, Field, field_validator

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DEFAULT_LOGO_THEME = {
    "primary_color": "#2563eb",
    "secondary_color": "#0f172a",
    "accent_color": "#22c55e",
    "sidebar_color": "#0f172a",
    "background_color": "#f8fafc",
    "text_color": "#0f172a",
    "theme_mode": "light",
    "theme_source": "preset",
    "preset_name": "professional_blue",
    "border_radius": 16,
}


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


class SchoolBrandingUpdate(BaseModel):
    logo_url: str | None = Field(default=None, max_length=500)
    favicon_url: str | None = Field(default=None, max_length=500)
    primary_color: str | None = Field(default=None, max_length=20)
    secondary_color: str | None = Field(default=None, max_length=20)
    accent_color: str | None = Field(default=None, max_length=20)
    sidebar_color: str | None = Field(default=None, max_length=20)
    background_color: str | None = Field(default=None, max_length=20)
    text_color: str | None = Field(default=None, max_length=20)
    theme_mode: str | None = Field(default=None, max_length=20)
    theme_source: str | None = Field(default=None, max_length=30)
    preset_name: str | None = Field(default=None, max_length=50)
    border_radius: int | None = Field(default=None, ge=6, le=28)

    @field_validator(
        "primary_color",
        "secondary_color",
        "accent_color",
        "sidebar_color",
        "background_color",
        "text_color",
    )
    @classmethod
    def validate_hex_color(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if not HEX_COLOR_RE.match(value):
            raise ValueError("Use a valid hex color like #2563eb")
        return value.lower()

    @field_validator("theme_mode")
    @classmethod
    def validate_theme_mode(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        value = value.lower()
        if value not in {"light", "dark", "auto"}:
            raise ValueError("Theme mode must be light, dark, or auto")
        return value

    @field_validator("theme_source")
    @classmethod
    def validate_theme_source(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        value = value.lower()
        if value not in {"preset", "manual", "logo_generated"}:
            raise ValueError("Theme source must be preset, manual, or logo_generated")
        return value


class SchoolBrandingRead(BaseModel):
    id: int
    school_id: int
    logo_url: str | None = None
    favicon_url: str | None = None
    primary_color: str
    secondary_color: str
    accent_color: str
    sidebar_color: str
    background_color: str
    text_color: str
    theme_mode: str
    theme_source: str
    preset_name: str
    border_radius: int

    model_config = {"from_attributes": True}


class SchoolBrandingPublic(BaseModel):
    school_name: str
    school_code: str
    logo_url: str | None = None
    primary_color: str
    secondary_color: str
    accent_color: str
    sidebar_color: str
    background_color: str
    text_color: str
    theme_mode: str
    theme_source: str
    preset_name: str
    border_radius: int


class LogoUploadResponse(BaseModel):
    logo_url: str
    branding: SchoolBrandingRead


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
