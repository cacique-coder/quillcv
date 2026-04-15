"""Add jobs table and job_id FK on saved_cvs.

Creates the ``jobs`` table, which links a user's profile to a specific job
application and stores AI-generated CV / cover letter outputs for that role.
Also adds a nullable ``job_id`` foreign key on ``saved_cvs`` so generated CVs
can be associated back to the originating Job.

Revision ID: 005_add_jobs_table
Revises: 004_add_password_reset_tokens
Create Date: 2026-04-02
"""

import sqlalchemy as sa

from alembic import op

revision = "005_add_jobs_table"
down_revision = "004_add_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the jobs table
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        # Job details
        sa.Column("job_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("job_title", sa.String(255), nullable=False, server_default=""),
        sa.Column("company_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("job_description", sa.Text, nullable=False),
        sa.Column("offer_appeal", sa.Text, nullable=False, server_default=""),
        # Generation config
        sa.Column("region", sa.String(5), nullable=False),
        sa.Column("template_id", sa.String(50), nullable=False, server_default=""),
        # Generated outputs (encrypted at rest)
        sa.Column("cv_data_json", sa.Text, nullable=True),
        sa.Column("cv_rendered_html", sa.Text, nullable=True),
        sa.Column("cover_letter_json", sa.Text, nullable=True),
        sa.Column("cover_letter_html", sa.Text, nullable=True),
        # Scores & review
        sa.Column("ats_original_score", sa.Integer, nullable=True),
        sa.Column("ats_generated_score", sa.Integer, nullable=True),
        sa.Column("quality_review_json", sa.Text, nullable=True),
        # Keywords (cached from extraction)
        sa.Column("keywords_json", sa.Text, nullable=True),
        # Lifecycle
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("attempt_id", sa.String(32), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])

    # 2. Add job_id FK column to saved_cvs
    op.add_column(
        "saved_cvs",
        sa.Column("job_id", sa.String(32), sa.ForeignKey("jobs.id"), nullable=True),
    )
    op.create_index("ix_saved_cvs_job_id", "saved_cvs", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_cvs_job_id", table_name="saved_cvs")
    op.drop_column("saved_cvs", "job_id")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
