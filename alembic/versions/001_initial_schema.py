"""Initial schema — baseline for existing database.

This migration represents the existing database schema created by
SQLAlchemy's Base.metadata.create_all during early development.
It makes no changes — it serves as the baseline so that future
migrations can be applied incrementally.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-14
"""

from alembic import op  # noqa: F401

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing tables are already in the database from the create_all era.
    # This migration is the baseline — no DDL changes required.
    pass


def downgrade() -> None:
    # Cannot downgrade the initial schema baseline.
    pass
