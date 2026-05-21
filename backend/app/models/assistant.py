import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "channel", "external_chat_id", name="uq_assistant_conversation_external"),
        Index("ix_assistant_conversations_user_channel", "user_id", "channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    external_chat_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    working_memory: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    llm_status: Mapped[str] = mapped_column(String(32), default="unknown", server_default="unknown", nullable=False)
    llm_recovered_notice_pending: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", lazy="selectin")
    messages = relationship("AssistantMessage", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin")
    pending_actions = relationship("AssistantPendingAction", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index("ix_assistant_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation = relationship("AssistantConversation", back_populates="messages", lazy="selectin")


class AssistantPendingAction(Base):
    __tablename__ = "assistant_pending_actions"
    __table_args__ = (
        Index("ix_assistant_pending_actions_conversation_status", "conversation_id", "status"),
        Index("ix_assistant_pending_actions_idempotency_key", "idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    conversation = relationship("AssistantConversation", back_populates="pending_actions", lazy="selectin")
