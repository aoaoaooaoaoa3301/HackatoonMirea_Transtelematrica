from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import date

from app.models.enums import TaskPriority, TaskType
from app.schemas.assistant import AssistantActionButton


class DigestRequest(BaseModel):
    scope: str  # "department" | "user" | "all"
    id: Optional[UUID] = None
    period: Optional[str] = "month"


class DigestResponse(BaseModel):
    summary: str
    key_points: List[str] = []


class RisksRequest(BaseModel):
    scope: str  # "department" | "user" | "all"
    id: Optional[UUID] = None


class RiskItem(BaseModel):
    task_id: UUID
    title: str
    risk_level: str  # "low" | "med" | "high"
    reason: str


class RisksResponse(BaseModel):
    items: List[RiskItem] = []


class OverloadItem(BaseModel):
    user_id: UUID
    full_name: str
    status: str  # "ok" | "warning" | "overload"
    suggestion: str


class OverloadResponse(BaseModel):
    items: List[OverloadItem] = []


class ParseTaskRequest(BaseModel):
    text: str


class ParseTaskResponse(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_suggestion: Optional[str] = None
    type: TaskType = TaskType.TASK


class SuggestAssigneeRequest(BaseModel):
    title: str
    description: Optional[str] = None
    department_id: Optional[UUID] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None


class AssigneeCandidate(BaseModel):
    user_id: UUID
    full_name: str
    score: float
    reason: str


class SuggestAssigneeResponse(BaseModel):
    candidates: List[AssigneeCandidate] = []


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None
    history: List[dict] = []


class ChatResponse(BaseModel):
    reply: str


class AssistantModelState(BaseModel):
    provider: str
    name: str
    available: bool


class AssistantMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    client_message_id: Optional[str] = None
    context: Optional[dict] = None


class AssistantStoredMessage(BaseModel):
    id: UUID
    role: str
    content: str


class AssistantMessageResponse(BaseModel):
    conversation_id: UUID
    message_id: Optional[UUID] = None
    text: str
    buttons: List[AssistantActionButton] = []
    pending_action: Optional[dict] = None
    referenced_task_ids: List[UUID] = []
    mode: str = "normal"
    model: AssistantModelState


class AssistantConversationResponse(BaseModel):
    conversation_id: UUID
    messages: List[AssistantStoredMessage] = []
    mode: str = "normal"
    model: AssistantModelState


class AssistantConfirmResponse(BaseModel):
    text: str
    buttons: List[AssistantActionButton] = []
    referenced_task_ids: List[UUID] = []


class GoalSummaryResponse(BaseModel):
    progress: float
    risks: List[RiskItem] = []
    summary: str
