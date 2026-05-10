"""Add tier column to users.

Supports tier-gated credit packs. Values: 'public' (default) | 'founder'.
Alpha pack buyers are automatically upgraded to 'founder' on payment success.

Revision ID: 008_add_user_tier
Revises: 007_add_credit_total_granted
Create Date: 2026-05-09
"""

import sqlalchemy as sa

from alembic import op

revision = "008_add_user_tier"
down_revision = "007_add_credit_total_granted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "tier",
            sa.String(20),
            nullable=False,
            server_default="public",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "tier")
