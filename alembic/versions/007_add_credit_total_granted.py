"""Add total_granted column to credits.

Distinguishes admin-issued credit grants from paid purchases. Without this,
admin grants inflate ``total_purchased`` and the user-facing "Purchased"
counter on the Account page lies. Existing rows are left at the default 0.

Revision ID: 007_add_credit_total_granted
Revises: 006_add_prompt_logging
Create Date: 2026-05-09
"""

import sqlalchemy as sa

from alembic import op

revision = "007_add_credit_total_granted"
down_revision = "006_add_prompt_logging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credits",
        sa.Column("total_granted", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("credits", "total_granted")
