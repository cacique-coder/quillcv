"""Add prompt_logging_eligible flag to users and create prompt_logs table.

Admin-gated prompt capture: an admin marks specific users as eligible to opt
in to sharing their prompts and responses. Users who are eligible see a
toggle in their account settings; opting in writes a ConsentRecord with
``consent_type='prompt_logging'`` and from then on every LLM prompt + response
generated for that user is mirrored to ``prompt_logs`` for admin review.

Revision ID: 006_add_prompt_logging
Revises: 005_add_jobs_table
Create Date: 2026-05-08
"""

import sqlalchemy as sa

from alembic import op

revision = "006_add_prompt_logging"
down_revision = "005_add_jobs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "prompt_logging_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "prompt_logs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("transaction_id", sa.String(36), nullable=False),
        sa.Column("attempt_id", sa.String(32), nullable=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("service", sa.String(50), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="cv"),
        sa.Column("model", sa.String(100), nullable=False, server_default=""),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prompt_logs_user_id", "prompt_logs", ["user_id"])
    op.create_index("ix_prompt_logs_transaction_id", "prompt_logs", ["transaction_id"])
    op.create_index("ix_prompt_logs_attempt_id", "prompt_logs", ["attempt_id"])
    op.create_index("ix_prompt_logs_created_at", "prompt_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_prompt_logs_created_at", table_name="prompt_logs")
    op.drop_index("ix_prompt_logs_attempt_id", table_name="prompt_logs")
    op.drop_index("ix_prompt_logs_transaction_id", table_name="prompt_logs")
    op.drop_index("ix_prompt_logs_user_id", table_name="prompt_logs")
    op.drop_table("prompt_logs")
    op.drop_column("users", "prompt_logging_eligible")
