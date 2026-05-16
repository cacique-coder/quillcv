"""Add feature_flags table for runtime feature gating.

Stores per-key boolean overrides editable from the admin UI. When a row
exists for a key, its ``enabled`` value wins over the registry default.
When no row exists, the registry default applies (often env-driven).

Revision ID: 012_add_feature_flags
Revises: 011_add_cv_references
Create Date: 2026-05-15
"""

import sqlalchemy as sa

from alembic import op

revision = "012_add_feature_flags"
down_revision = "011_add_cv_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
