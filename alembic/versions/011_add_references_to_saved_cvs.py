"""Add references_json column to saved_cvs.

Stores the actual reference values (encrypted at rest with the server Fernet
key) on the SavedCV row so that references survive vault state divergence and
sessions without ``_pii_password``. The PIIRedactor still tokenises references
inside ``cv_data_json`` at save time; on load this column overrides whatever
was tokenised so references are always restored to plaintext.

Revision ID: 011_add_cv_references
Revises: 010_add_cv_voice_fields
Create Date: 2026-05-10
"""

import sqlalchemy as sa

from alembic import op

revision = "011_add_cv_references"
down_revision = "010_add_cv_voice_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "saved_cvs",
        sa.Column("references_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saved_cvs", "references_json")
