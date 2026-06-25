from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, Field, field_validator


DAY_VALUES = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}


class TimetablePeriodBase(BaseModel):
    period_number: int = Field(ge=1, le=20)
    name: str = Field(min_length=1, max_length=120)
    start_time: time | None = None
    end_time: time | None = None
    is_break: bool = False
    is_active: bool = True

    @field_validator("end_time")
    @classmethod
    def validate_time_order(cls, value: time | None, info: Any):
        start_time = info.data.get("start_time")
        if value and start_time and value <= start_time:
            raise ValueError("End time must be after start time")
        return value


class TimetablePeriodCreate(TimetablePeriodBase):
    pass


class TimetablePeriodUpdate(BaseModel):
    period_number: int | None = Field(default=None, ge=1, le=20)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    start_time: time | None = None
    end_time: time | None = None
    is_break: bool | None = None
    is_active: bool | None = None

    @field_validator("end_time")
    @classmethod
    def validate_time_order(cls, value: time | None, info: Any):
        start_time = info.data.get("start_time")
        if value and start_time and value <= start_time:
            raise ValueError("End time must be after start time")
        return value


class TimetablePeriodRead(TimetablePeriodBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimetableDayBase(BaseModel):
    day_of_week: str = Field(min_length=3, max_length=20)
    display_name: str = Field(min_length=2, max_length=80)
    sort_order: int = Field(default=1, ge=1, le=7)
    is_active: bool = True

    @field_validator("day_of_week")
    @classmethod
    def normalize_day(cls, value: str):
        normalized = value.strip().upper()
        if normalized not in DAY_VALUES:
            raise ValueError("day_of_week must be one of MONDAY to SUNDAY")
        return normalized


class TimetableDayCreate(TimetableDayBase):
    pass


class TimetableDayUpdate(BaseModel):
    day_of_week: str | None = Field(default=None, min_length=3, max_length=20)
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    sort_order: int | None = Field(default=None, ge=1, le=7)
    is_active: bool | None = None

    @field_validator("day_of_week")
    @classmethod
    def normalize_day(cls, value: str | None):
        if value is None:
            return value
        normalized = value.strip().upper()
        if normalized not in DAY_VALUES:
            raise ValueError("day_of_week must be one of MONDAY to SUNDAY")
        return normalized


class TimetableDayRead(TimetableDayBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimetableEntryBase(BaseModel):
    class_id: int
    section_id: int | None = None
    section_name: str | None = None
    day_id: int
    period_id: int
    subject_id: int | None = None
    teacher_id: int | None = None
    room: str | None = Field(default=None, max_length=120)
    note: str | None = None
    academic_session_id: int | None = None
    is_active: bool = True


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryUpdate(BaseModel):
    class_id: int | None = None
    section_id: int | None = None
    section_name: str | None = None
    day_id: int | None = None
    period_id: int | None = None
    subject_id: int | None = None
    teacher_id: int | None = None
    room: str | None = Field(default=None, max_length=120)
    note: str | None = None
    academic_session_id: int | None = None
    is_active: bool | None = None


class TimetableEntryRead(TimetableEntryBase):
    id: int
    class_name: str | None = None
    section_name: str | None = None
    day_name: str | None = None
    day_of_week: str | None = None
    day_sort_order: int | None = None
    period_name: str | None = None
    period_number: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    subject_name: str | None = None
    teacher_name: str | None = None
    academic_session_name: str | None = None
    created_at: datetime
    updated_at: datetime


class TimetableMetaItem(BaseModel):
    id: int
    name: str
    extra: str | None = None


class TimetableMetaResponse(BaseModel):
    classes: list[TimetableMetaItem]
    sections: list[TimetableMetaItem]
    subjects: list[TimetableMetaItem]
    teachers: list[TimetableMetaItem]
    periods: list[TimetablePeriodRead]
    days: list[TimetableDayRead]
    academic_sessions: list[TimetableMetaItem]
    current_academic_session_id: int | None = None


class TimetableGridResponse(BaseModel):
    mode: str
    title: str
    entries: list[TimetableEntryRead]
    periods: list[TimetablePeriodRead]
    days: list[TimetableDayRead]
