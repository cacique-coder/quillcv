"""Add role column to users table.

Adds a non-nullable `role` VARCHAR(20) column with a server-side default
of 'consumer'. All existing rows receive the default automatically.

Revision ID: 002_add_role
Revises: 001_initial
Create Date: 2026-03-14
"""

import sqlalchemy as sa

from alembic import op

revision = "002_add_role"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), server_default="consumer", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
