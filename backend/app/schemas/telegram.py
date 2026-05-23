from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.assistant import AssistantActionButton


class TelegramStatusResponse(BaseModel):
    connected: bool
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None
    linked_at: Optional[datetime] = None
    bot_username: Optional[str] = None


class TelegramLinkStartResponse(BaseModel):
    code: str
    expires_at: datetime
    instruction: str
    # Telegram deep link (https://t.me/<bot>?start=<code>). When the user opens
    # it — or scans its QR — Telegram launches the bot with /start <code> and the
    # account is linked without typing the code manually. Null if the bot
    # username isn't configured (then fall back to the manual /link CODE flow).
    deep_link: Optional[str] = None
    bot_username: Optional[str] = None


class TaskLink(BaseModel):
    id: str
    title: str
    url: str


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
    # Tasks referenced by this reply, as clickable links into the web app.
    # The bot renders them as inline URL buttons so a mentioned/created task
    # is always reachable from the chat.
    task_links: list[TaskLink] = Field(default_factory=list)
