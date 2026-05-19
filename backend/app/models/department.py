import uuid
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Optional, List

from app.core.db import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    head_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    parent: Mapped[Optional["Department"]] = relationship(
        "Department", remote_side="Department.id", foreign_keys=[parent_id], lazy="selectin"
    )
    children: Mapped[List["Department"]] = relationship(
        "Department", back_populates="parent", foreign_keys=[parent_id], lazy="selectin"
    )
    head_user: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[head_user_id], lazy="selectin"
    )
    members: Mapped[List["User"]] = relationship(  # noqa: F821
        "User", back_populates="department", foreign_keys="User.department_id", lazy="selectin"
    )
