from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from app.models.enums import UserRole


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: UserRole = UserRole.EMPLOYEE
    department_id: Optional[UUID] = None
    skills: List[str] = []
    seniority: Optional[str] = None
    capacity_hours_per_week: int = 40


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    department_id: Optional[UUID] = None
    skills: Optional[List[str]] = None
    seniority: Optional[str] = None
    capacity_hours_per_week: Optional[int] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    department_id: Optional[UUID] = None
    department_name: Optional[str] = None
    skills: List[str] = []
    seniority: Optional[str] = None
    capacity_hours_per_week: int = 40
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkloadOut(BaseModel):
    open_tasks: int
    weighted_load: float
    overdue_count: int
    at_risk_count: int
    capacity_util: float
