"""Add per-CV professional voice fields to saved_cvs.

Stores the ``self_description``, ``values`` and ``offer_appeal`` that were
used to tailor each saved CV so that re-running the wizard from a saved CV
preserves the original voice. ``values`` is renamed to ``values_text`` in
the column to avoid colliding with the SQL/Python keyword.

Revision ID: 010_add_cv_voice_fields
Revises: 009_prompt_log_status
Create Date: 2026-05-10
"""

import sqlalchemy as sa

from alembic import op

revision = "010_add_cv_voice_fields"
down_revision = "009_prompt_log_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "saved_cvs",
        sa.Column("self_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "saved_cvs",
        sa.Column("values_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "saved_cvs",
        sa.Column("offer_appeal", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saved_cvs", "offer_appeal")
    op.drop_column("saved_cvs", "values_text")
    op.drop_column("saved_cvs", "self_description")
