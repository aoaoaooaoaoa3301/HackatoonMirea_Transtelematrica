"""ai first assistant conversations

Revision ID: 0004_ai_first_assistant
Revises: 0003
Create Date: 2026-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_ai_first_assistant"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_chat_id", sa.String(255), nullable=True),
        sa.Column("working_memory", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("llm_status", sa.String(32), server_default="unknown", nullable=False),
        sa.Column("llm_recovered_notice_pending", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "channel", "external_chat_id", name="uq_assistant_conversation_external"),
    )
    op.create_index("ix_assistant_conversations_user_channel", "assistant_conversations", ["user_id", "channel"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_assistant_messages_conversation_created", "assistant_messages", ["conversation_id", "created_at"])

    op.create_table(
        "assistant_pending_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_assistant_pending_actions_conversation_status", "assistant_pending_actions", ["conversation_id", "status"])
    op.create_index("ix_assistant_pending_actions_idempotency_key", "assistant_pending_actions", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_assistant_pending_actions_idempotency_key", table_name="assistant_pending_actions")
    op.drop_index("ix_assistant_pending_actions_conversation_status", table_name="assistant_pending_actions")
    op.drop_table("assistant_pending_actions")
    op.drop_index("ix_assistant_messages_conversation_created", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_conversations_user_channel", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
