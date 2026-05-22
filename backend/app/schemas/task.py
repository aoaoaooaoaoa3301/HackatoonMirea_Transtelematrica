from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List, Any
from datetime import date, datetime

from app.models.enums import TaskType, TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    type: Optional[TaskType] = None
    parent_id: Optional[UUID] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.NEW
    progress: int = Field(default=0, ge=0, le=100)
    assigned_department_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[TaskType] = None
    parent_id: Optional[UUID] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    assigned_department_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None


class CommentCreate(BaseModel):
    body: str


class CommentUpdate(BaseModel):
    body: str


class CommentOut(BaseModel):
    id: UUID
    task_id: UUID
    author_id: UUID
    author_name: Optional[str] = None
    body: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class HistoryOut(BaseModel):
    id: UUID
    task_id: UUID
    actor_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    event_type: str
    payload: Optional[Any] = None
    at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: UUID
    type: TaskType
    title: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: TaskPriority
    status: TaskStatus
    progress: int = 0
    assigned_department_id: Optional[UUID] = None
    assigned_department_name: Optional[str] = None
    assignee_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    period_bucket: Optional[str] = None
    children_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TaskTreeNode(BaseModel):
    id: UUID
    type: TaskType
    title: str
    status: TaskStatus
    priority: TaskPriority
    progress: int = 0
    assignee_id: Optional[UUID] = None
    assignee_name: Optional[str] = None
    assigned_department_name: Optional[str] = None
    due_date: Optional[date] = None
    period_bucket: Optional[str] = None
    children: List["TaskTreeNode"] = []

    model_config = {"from_attributes": True}


class ParentChainItem(BaseModel):
    id: UUID
    type: TaskType
    title: str

    model_config = {"from_attributes": True}


class TaskDetailOut(TaskOut):
    children: List[TaskOut] = []
    parent_chain: List[ParentChainItem] = []
    comments: List[CommentOut] = []
    history: List[HistoryOut] = []
