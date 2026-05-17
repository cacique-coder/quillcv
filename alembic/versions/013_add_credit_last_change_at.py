"""Add last_change_at to credits for stale-cache detection.

The AuthContextMiddleware compares Credit.last_change_at against the
session's cached_balance_set_at to decide whether to refetch the balance
from the database.  This lets an admin grant (or any out-of-band balance
change) appear in the target user's nav bar on their very next request —
without requiring a log-out/log-in cycle.

Existing rows receive the current timestamp via server_default so the column
is never NULL and the middleware's comparison is always valid.

Revision ID: 013_add_credit_last_change_at
Revises: 012_add_feature_flags
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from sqlalchemy import func

from alembic import op

revision = "013_add_credit_last_change_at"
down_revision = "012_add_feature_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credits",
        sa.Column(
            "last_change_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("credits", "last_change_at")
