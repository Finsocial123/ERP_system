#Chats
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import Annotated

class ChatBase(BaseModel):
    # user_id: int | None = None
    content: Annotated[str, Field(min_length=1, max_length=4000)]

class ChatRequest(ChatBase):
    lesson_id: int | None = None
    web_search: bool = False
    enhance_prompt: bool = False
    language: str = "en"
    pass

class ChatShareEmailRequest(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=20000)]
    to_email: EmailStr | None = None
    subject: Annotated[str | None, Field(max_length=200)] = None
    lesson_title: Annotated[str | None, Field(max_length=200)] = None
    course_title: Annotated[str | None, Field(max_length=200)] = None

    @field_validator("to_email", mode="before")
    @classmethod
    def blank_email_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

class ChatShareTelegramRequest(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=20000)]
    chat_id: Annotated[str | None, Field(max_length=128)] = None
    lesson_title: Annotated[str | None, Field(max_length=200)] = None
    course_title: Annotated[str | None, Field(max_length=200)] = None

    @field_validator("chat_id", mode="before")
    @classmethod
    def blank_chat_id_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

class ChatShareResponse(BaseModel):
    ok: bool = True
    channel: str
    message: str

class ChatResponse(ChatBase):
    model_config = ConfigDict(from_attributes=True)

    content: str
