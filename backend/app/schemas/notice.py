from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.notice import NoticePriority, NoticeStatus
from app.models.user import UserRole


class NoticeAudienceOut(BaseModel):
    id: int
    role: str

    model_config = {"from_attributes": True}

class AvailableClassOut(BaseModel):
    class_id: int
    class_name: str
    section_id: int | None
    section_name: str | None

class NoticeClassAudienceOut(BaseModel):
    id: int
    class_id: int
    section_id: int | None = None
    section_name: str | None = None

    model_config = {"from_attributes": True} 

class NoticeBase(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)]
    content: Annotated[str, Field(min_length=1)]
    priority: NoticePriority = NoticePriority.NORMAL
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    audience_roles: list[UserRole] = []

    @model_validator(mode="after")
    def check_expiry_after_publish(self) -> "NoticeBase":
        if self.publish_at and self.expires_at:
            if self.expires_at <= self.publish_at:
                raise ValueError("expires_at must be after publish_at")
        return self


class NoticeUpdate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)] | None = None
    content: str | None = None
    priority: NoticePriority | None = None
    status: NoticeStatus | None = None
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    audience_roles: list[UserRole] | None = None
    audience_class_ids: list[int] | None = None     
    audience_section_ids: list[int] | None = None   


    @model_validator(mode="after")
    def check_expiry_after_publish(self) -> "NoticeUpdate":
        """Validate that expires_at is after publish_at when both are provided."""
        if self.publish_at and self.expires_at:
            if self.expires_at <= self.publish_at:
                raise ValueError("expires_at must be after publish_at")
        return self


class AuthorOut(BaseModel):
    id: int
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class NoticeOut(BaseModel):
    id: int
    school_id: int
    title: str
    content: str
    priority: str
    status: str
    is_pinned: bool
    publish_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    author: AuthorOut | None
    audiences: list[NoticeAudienceOut]
    read_count: int = 0
    is_read: bool = False 
    class_audiences: list[NoticeClassAudienceOut] = []
    
    model_config = {"from_attributes": True}


class NoticePinUpdate(BaseModel):
    is_pinned: bool


class NoticeListOut(BaseModel):
    items: list[NoticeOut]
    total: int
    unread_count: int


class NoticeEnhanceRequest(BaseModel):
    content: str

class NoticeEnhanceOut(BaseModel):
    original: str
    enhanced: str

class NoticeGenerateRequest(BaseModel):
    description: str

class NoticeGenerateOut(BaseModel):
    description: str
    generated: str


class NoticeCreate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=255)]
    content: Annotated[str, Field(min_length=1)]
    enhance: bool = False
    priority: NoticePriority = NoticePriority.NORMAL
    status: NoticeStatus = NoticeStatus.PUBLISHED
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    audience_roles: list[UserRole] = []
    audience_class_ids: list[int] = []   
    audience_section_ids: list[int] = [] 

    @model_validator(mode="after")
    def check_expiry_after_publish(self) -> "NoticeCreate":
        """Validate that expires_at is after publish_at when both are provided."""
        if self.publish_at and self.expires_at:
            if self.expires_at <= self.publish_at:
                raise ValueError("expires_at must be after publish_at")
        return self
    
    @model_validator(mode="after")
    def check_class_section_lengths(self) -> "NoticeCreate":
        if self.audience_section_ids and len(self.audience_section_ids) != len(self.audience_class_ids):
            raise ValueError("audience_section_ids must have the same length as audience_class_ids")
        return self


