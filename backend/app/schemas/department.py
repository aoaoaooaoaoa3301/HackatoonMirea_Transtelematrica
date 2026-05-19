from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime


class DepartmentCreate(BaseModel):
    name: str
    parent_id: Optional[UUID] = None
    head_user_id: Optional[UUID] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[UUID] = None
    head_user_id: Optional[UUID] = None


class DepartmentOut(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    head_user_id: Optional[UUID] = None
    head_user_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DepartmentMemberOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    seniority: Optional[str] = None
    skills: List[str] = []

    model_config = {"from_attributes": True}


class DepartmentDetailOut(DepartmentOut):
    members: List[DepartmentMemberOut] = []
    children: List[DepartmentOut] = []
