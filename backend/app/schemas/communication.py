from datetime import date, datetime, time
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.communication import (
    CommunicationPriority,
    CommunicationStatus,
    ComplaintStatus,
)
from app.models.user import UserRole


class UserMini(BaseModel):
    id: int
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class AnnouncementCreate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)]
    message: Annotated[str, Field(min_length=1)]
    priority: CommunicationPriority = CommunicationPriority.NORMAL
    status: CommunicationStatus = CommunicationStatus.PUBLISHED
    audience_roles: list[UserRole] = []
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def check_window(self) -> "AnnouncementCreate":
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class AnnouncementUpdate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)] | None = None
    message: str | None = None
    priority: CommunicationPriority | None = None
    status: CommunicationStatus | None = None
    audience_roles: list[UserRole] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def check_window(self) -> "AnnouncementUpdate":
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class AnnouncementOut(BaseModel):
    id: int
    title: str
    message: str
    priority: str
    status: str
    audience_roles: list[str] = []
    start_at: datetime | None = None
    end_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    author: UserMini | None = None

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)]
    description: str | None = None
    event_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    status: CommunicationStatus = CommunicationStatus.PUBLISHED
    audience_roles: list[UserRole] = []

    @model_validator(mode="after")
    def check_event_range(self) -> "EventCreate":
        if self.end_date and self.end_date < self.event_date:
            raise ValueError("end_date cannot be before event_date")
        if self.start_time and self.end_time and self.end_time <= self.start_time and not self.end_date:
            raise ValueError("end_time must be after start_time for same-day events")
        return self


class EventUpdate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)] | None = None
    description: str | None = None
    event_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    status: CommunicationStatus | None = None
    audience_roles: list[UserRole] | None = None


class EventOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    event_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    category: str | None = None
    status: str
    audience_roles: list[str] = []
    created_at: datetime
    updated_at: datetime
    author: UserMini | None = None

    model_config = {"from_attributes": True}


class ComplaintCreate(BaseModel):
    subject: Annotated[str, Field(min_length=3, max_length=255)]
    description: Annotated[str, Field(min_length=1)]
    category: str | None = Field(default=None, max_length=120)
    priority: CommunicationPriority = CommunicationPriority.NORMAL
    is_anonymous: bool = False


class ComplaintUpdate(BaseModel):
    subject: Annotated[str, Field(min_length=3, max_length=255)] | None = None
    description: str | None = None
    category: str | None = Field(default=None, max_length=120)
    priority: CommunicationPriority | None = None
    status: ComplaintStatus | None = None
    assigned_to: int | None = None
    action_taken: str | None = None
    is_anonymous: bool | None = None


class ComplaintOut(BaseModel):
    id: int
    subject: str
    description: str
    category: str | None = None
    priority: str
    status: str
    action_taken: str | None = None
    is_anonymous: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    creator: UserMini | None = None
    assignee: UserMini | None = None

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)]
    message: Annotated[str, Field(min_length=1)]
    category: str | None = Field(default="GENERAL", max_length=80)
    priority: CommunicationPriority = CommunicationPriority.NORMAL
    target_role: UserRole | None = None
    target_user_id: int | None = None
    link: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None


class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    category: str | None = None
    priority: str
    target_role: str | None = None
    target_user_id: int | None = None
    link: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    is_read: bool = False
    author: UserMini | None = None

    model_config = {"from_attributes": True}


class CommunicationOverview(BaseModel):
    announcements: int
    upcoming_events: int
    open_complaints: int
    unread_notifications: int
