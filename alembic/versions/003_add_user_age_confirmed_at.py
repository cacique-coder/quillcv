"""Add age_confirmed_at column to users table.

Required by COPPA (US), LGPD Art. 14 (BR), and Ley 1581 (CO) for
recording when a user confirmed they are 18 years or older.

Revision ID: 003_add_age_confirmed_at
Revises: 002_add_role
Create Date: 2026-03-14
"""

import sqlalchemy as sa

from alembic import op

revision = "003_add_age_confirmed_at"
down_revision = "002_add_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "age_confirmed_at")
