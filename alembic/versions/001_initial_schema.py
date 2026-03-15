"""Initial schema — creates all baseline tables for fresh and existing databases.

This migration creates the full initial schema as it existed before any
incremental migrations were added. It is safe to run on both fresh databases
(tables do not yet exist) and existing databases (existence checks prevent
errors if tables are already present).

Tables created here reflect the schema BEFORE migrations 002, 003, and 004
were applied. Notably:
  - users.role is NOT present (added by 002)
  - users.age_confirmed_at is NOT present (added by 003)

Revision ID: 001_initial
Revises:
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False, server_default=""),
            sa.Column("password_hash", sa.String(255), nullable=True),
            sa.Column("provider", sa.String(50), nullable=True),
            sa.Column("provider_id", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_users_email", "users", ["email"])

    if "credits" not in existing:
        op.create_table(
            "credits",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_purchased", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_credits_user_id", "credits", ["user_id"])

    if "payments" not in existing:
        op.create_table(
            "payments",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("stripe_session_id", sa.String(255), nullable=False),
            sa.Column("stripe_payment_intent", sa.String(255), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
            sa.Column("credits_granted", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("stripe_session_id"),
        )
        op.create_index("ix_payments_user_id", "payments", ["user_id"])

    if "webauthn_credentials" not in existing:
        op.create_table(
            "webauthn_credentials",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("credential_id", sa.Text(), nullable=False),
            sa.Column("public_key", sa.Text(), nullable=False),
            sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("name", sa.String(255), nullable=False, server_default="Passkey"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("credential_id"),
        )
        op.create_index("ix_webauthn_credentials_user_id", "webauthn_credentials", ["user_id"])

    if "saved_cvs" not in existing:
        op.create_table(
            "saved_cvs",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("attempt_id", sa.String(32), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("label", sa.String(255), nullable=False, server_default=""),
            sa.Column("job_title", sa.String(255), nullable=False, server_default=""),
            sa.Column("region", sa.String(5), nullable=False),
            sa.Column("template_id", sa.String(50), nullable=False),
            sa.Column("markdown", sa.Text(), nullable=False),
            sa.Column("cv_data_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_saved_cvs_user_id", "saved_cvs", ["user_id"])
        op.create_index("ix_saved_cvs_attempt_id", "saved_cvs", ["attempt_id"])

    if "expressions_of_interest" not in existing:
        op.create_table(
            "expressions_of_interest",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False, server_default=""),
            sa.Column("source", sa.String(50), nullable=False, server_default="signup"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_expressions_of_interest_email", "expressions_of_interest", ["email"])

    if "invitations" not in existing:
        op.create_table(
            "invitations",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("code", sa.String(16), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("credits", sa.Integer(), nullable=False),
            sa.Column("note", sa.String(255), nullable=False, server_default=""),
            sa.Column("redeemed_by", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_invitations_code", "invitations", ["code"])
        op.create_index("ix_invitations_email", "invitations", ["email"])

    if "pii_vault" not in existing:
        op.create_table(
            "pii_vault",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("salt", sa.String(64), nullable=False, server_default=""),
            sa.Column("encrypted_data", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_pii_vault_user_id", "pii_vault", ["user_id"])

    if "consent_records" not in existing:
        op.create_table(
            "consent_records",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("consent_type", sa.String(60), nullable=False),
            sa.Column("granted", sa.Boolean(), nullable=False),
            sa.Column("email", sa.String(255), nullable=False, server_default=""),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("policy_version", sa.String(20), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
        op.create_index("ix_consent_records_consent_type", "consent_records", ["consent_type"])
        op.create_index("ix_consent_records_email", "consent_records", ["email"])
        op.create_index("ix_consent_records_created_at", "consent_records", ["created_at"])

    if "api_request_logs" not in existing:
        op.create_table(
            "api_request_logs",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("transaction_id", sa.String(36), nullable=False),
            sa.Column("attempt_id", sa.String(32), nullable=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("service", sa.String(50), nullable=False),
            sa.Column("model", sa.String(100), nullable=False),
            sa.Column("prompt_chars", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cache_creation_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="success"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_api_request_logs_transaction_id", "api_request_logs", ["transaction_id"])
        op.create_index("ix_api_request_logs_attempt_id", "api_request_logs", ["attempt_id"])
        op.create_index("ix_api_request_logs_user_id", "api_request_logs", ["user_id"])
        op.create_index("ix_api_request_logs_created_at", "api_request_logs", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing = inspector.get_table_names()

    # Drop in reverse order to respect foreign key dependencies.
    for table in [
        "api_request_logs",
        "consent_records",
        "pii_vault",
        "invitations",
        "expressions_of_interest",
        "saved_cvs",
        "webauthn_credentials",
        "payments",
        "credits",
        "users",
    ]:
        if table in existing:
            op.drop_table(table)
