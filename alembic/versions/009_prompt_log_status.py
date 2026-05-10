"""Add status and error_message to prompt_logs.

Every consented prompt is now persisted, including failures (timeouts, API
errors). ``status`` mirrors ``api_request_logs.status`` and ``error_message``
captures the failure detail when relevant. Existing rows default to
``'success'`` via ``server_default`` so the migration is non-breaking.

Revision ID: 009_prompt_log_status
Revises: 008_add_user_tier
Create Date: 2026-05-10
"""

import sqlalchemy as sa

from alembic import op

revision = "009_prompt_log_status"
down_revision = "008_add_user_tier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prompt_logs",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'success'"),
        ),
    )
    op.add_column(
        "prompt_logs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prompt_logs", "error_message")
    op.drop_column("prompt_logs", "status")
