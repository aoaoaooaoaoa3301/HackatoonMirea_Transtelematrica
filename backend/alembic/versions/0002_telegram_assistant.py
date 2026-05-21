"""Add Telegram assistant tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("telegram_first_name", sa.String(255), nullable=True),
        sa.Column("telegram_last_name", sa.String(255), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("linked_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_telegram_accounts_telegram_user_id", "telegram_accounts", ["telegram_user_id"], unique=True)

    op.create_table(
        "telegram_link_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_telegram_link_codes_code", "telegram_link_codes", ["code"], unique=True)

    op.create_table(
        "telegram_sessions",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_task_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("pending_action", postgresql.JSONB(), nullable=True),
        sa.Column("last_intent", sa.String(64), nullable=True),
        sa.Column("last_scope", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("telegram_sessions")
    op.drop_index("ix_telegram_link_codes_code", table_name="telegram_link_codes")
    op.drop_table("telegram_link_codes")
    op.drop_index("ix_telegram_accounts_telegram_user_id", table_name="telegram_accounts")
    op.drop_table("telegram_accounts")
