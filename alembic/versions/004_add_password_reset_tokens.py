"""Add password_reset_tokens table.

Stores single-use, TTL-bound password reset tokens for the forgot-password flow.

Revision ID: 004_add_password_reset_tokens
Revises: 003_add_age_confirmed_at
Create Date: 2026-03-15
"""

import sqlalchemy as sa

from alembic import op

revision = "004_add_password_reset_tokens"
down_revision = "003_add_age_confirmed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "password_reset_tokens" not in inspector.get_table_names():
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
