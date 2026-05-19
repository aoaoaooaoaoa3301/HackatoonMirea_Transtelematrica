import uuid
from sqlalchemy import String, Boolean, Integer, ForeignKey, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
from typing import Optional

from app.core.db import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role", create_constraint=False), nullable=False, default=UserRole.EMPLOYEE)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    skills: Mapped[list] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    seniority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    capacity_hours_per_week: Mapped[int] = mapped_column(Integer, default=40, server_default="40")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    department: Mapped[Optional["Department"]] = relationship(  # noqa: F821
        "Department", back_populates="members", foreign_keys=[department_id], lazy="selectin"
    )
