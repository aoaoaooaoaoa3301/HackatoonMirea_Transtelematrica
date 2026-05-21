from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AssistantActionButton(BaseModel):
    label: str
    callback_data: str


class AssistantResponse(BaseModel):
    text: str
    buttons: list[AssistantActionButton] = Field(default_factory=list)
    task_ids: list[UUID] = Field(default_factory=list)
    pending_action: Optional[dict] = None
    intent: Optional[str] = None
    scope: Optional[dict] = None
