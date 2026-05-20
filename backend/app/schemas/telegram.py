from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.assistant import AssistantActionButton


class TelegramStatusResponse(BaseModel):
    connected: bool
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None
    linked_at: Optional[datetime] = None


class TelegramLinkStartResponse(BaseModel):
    code: str
    expires_at: datetime
    instruction: str


class TelegramLinkConfirmRequest(BaseModel):
    telegram_user_id: int
    code: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramCommandRequest(BaseModel):
    telegram_user_id: int
    message: str


class TelegramConfirmActionRequest(BaseModel):
    telegram_user_id: int
    callback_data: str


class TelegramCommandResponse(BaseModel):
    text: str
    buttons: list[AssistantActionButton] = Field(default_factory=list)
