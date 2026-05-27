
#Chats
from pydantic import BaseModel, ConfigDict, Field
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

class ChatResponse(ChatBase):
    model_config = ConfigDict(from_attributes=True)

    content: str

