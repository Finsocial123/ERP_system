from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SchoolBranding(Base):
    __tablename__ = "school_branding"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), unique=True, index=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#2563eb")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#0f172a")
    accent_color: Mapped[str] = mapped_column(String(20), default="#22c55e")
    sidebar_color: Mapped[str] = mapped_column(String(20), default="#0f172a")
    background_color: Mapped[str] = mapped_column(String(20), default="#f8fafc")
    text_color: Mapped[str] = mapped_column(String(20), default="#0f172a")
    theme_mode: Mapped[str] = mapped_column(String(20), default="light")
    theme_source: Mapped[str] = mapped_column(String(30), default="preset")
    preset_name: Mapped[str] = mapped_column(String(50), default="professional_blue")
    border_radius: Mapped[int] = mapped_column(Integer, default=16)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school = relationship("School", back_populates="branding")
