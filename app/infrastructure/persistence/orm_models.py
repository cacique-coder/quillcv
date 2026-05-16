"""SQLAlchemy models for users, credits, payments, and WebAuthn credentials."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.database import Base


def _utcnow():
    return datetime.now(UTC)


def _uuid():
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # OAuth fields
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # google, github
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    role: Mapped[str] = mapped_column(String(20), default="consumer")  # consumer, admin
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="public",
        server_default="public",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Admin-gated flag — when True, the user sees a prompt-logging consent
    # toggle in account settings. Without this flag the toggle is hidden and no
    # prompts are captured for the user. Set/unset via /admin/users/{id}.
    prompt_logging_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Age gate — timestamp when the user confirmed they are 18 years or older.
    # Required by COPPA (US), LGPD Art. 14 (BR), and Ley 1581 (CO).
    age_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    credits: Mapped[list["Credit"]] = relationship(back_populates="user", lazy="select")
    webauthn_credentials: Mapped[list["WebAuthnCredential"]] = relationship(back_populates="user", lazy="select")
    consent_records: Mapped[list["ConsentRecord"]] = relationship(back_populates="user", lazy="select")


class Credit(Base):
    __tablename__ = "credits"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    total_purchased: Mapped[int] = mapped_column(Integer, default=0)
    total_granted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="credits")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_payment_intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    credits_granted: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(255), default="Passkey")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="webauthn_credentials")


class SavedCV(Base):
    """Stored CV content — both AI-generated and manually built."""
    __tablename__ = "saved_cvs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True, index=True)
    attempt_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Link to the Job that produced this CV (nullable for legacy rows and builder CVs).
    job_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("jobs.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "ai" or "builder"
    label: Mapped[str] = mapped_column(String(255), default="")  # user-chosen name for this CV
    job_title: Mapped[str] = mapped_column(String(255), default="")  # target job title (optional)
    region: Mapped[str] = mapped_column(String(5), nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)  # sanitized markdown content
    cv_data_json: Mapped[str] = mapped_column(Text, nullable=False)  # structured CV data as JSON
    # Per-CV professional voice — the values used at generation time so the
    # voice survives a re-run from this saved CV. Plaintext (matches
    # ``Job.offer_appeal`` precedent).
    self_description: Mapped[str] = mapped_column(Text, default="")
    values_text: Mapped[str] = mapped_column(Text, default="")
    offer_appeal: Mapped[str] = mapped_column(Text, default="")
    # Encrypted JSON list of {name, email, phone} reference dicts. When
    # populated this is the source of truth for references (overrides whatever
    # the PIIRedactor tokenised inside ``cv_data_json``). Encryption is handled
    # at the cv_repo layer with the server Fernet key.
    references_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Job(Base):
    """A target job application — links a user's profile to a specific role.

    Lifecycle statuses:
        draft       — created but generation not yet started
        generating  — AI generation in progress
        complete    — CV and/or cover letter generated successfully
        error       — generation failed; see quality_review_json for details
    """
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)

    # Job details
    job_url: Mapped[str] = mapped_column(String(2048), default="")
    job_title: Mapped[str] = mapped_column(String(255), default="")
    company_name: Mapped[str] = mapped_column(String(255), default="")
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    offer_appeal: Mapped[str] = mapped_column(Text, default="")

    # Generation config
    region: Mapped[str] = mapped_column(String(5), nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), default="")

    # Generated outputs (encrypted at rest with the server Fernet key)
    cv_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_rendered_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scores & review
    ats_original_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_generated_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_review_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Keywords (cached from extraction)
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="draft")
    attempt_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # bridge to legacy attempts

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class ExpressionOfInterest(Base):
    """Pre-launch interest capture — records emails before public signup opens."""
    __tablename__ = "expressions_of_interest"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(50), default="signup")  # where they signed up from
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Invitation(Base):
    """Admin-issued invitation codes that grant credits on redemption."""
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="")
    redeemed_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PIIVault(Base):
    """Encrypted PII vault — stores sensitive identity fields per user.

    For password users the data is encrypted with a key derived from their
    password (PBKDF2-HMAC-SHA256).  For OAuth users the server Fernet key is
    used instead (salt is empty string in that case).

    Fields stored inside ``encrypted_data`` (as a JSON blob):
        full_name, email, phone, dob, document_id,
        references (list of {name, email, phone})
    """
    __tablename__ = "pii_vault"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    # Hex-encoded random salt used for PBKDF2 key derivation.
    # Empty string for OAuth users (server-key mode).
    salt: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # Fernet-encrypted JSON blob containing PII fields
    encrypted_data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class ConsentRecord(Base):
    """Audit trail for all consent actions — required by LGPD, Ley 1581, CPRA.

    consent_type values:
        "age_verification"           — user confirmed they are 18+
        "sensitive_data_dob"         — consent to process date of birth
        "sensitive_data_document_id" — consent to process national ID / cédula
        "sensitive_data_photo"       — consent to process CV photo
        "terms_acceptance"           — acceptance of terms of service
        "privacy_policy_acceptance"  — acceptance of privacy policy
        "ccpa_opt_out"               — CCPA/CPRA Do Not Sell or Share request

    user_id is nullable so that unauthenticated visitors can submit CCPA opt-out
    requests without having a QuillCV account.
    """
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    # Nullable: unauthenticated CCPA opt-out requests have no user_id.
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True, index=True
    )
    # One of the consent_type values listed above
    consent_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # True = consent granted, False = consent withheld / withdrawn
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Email at time of submission — required for CCPA opt-out audit trail.
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Policy version string at time of consent (e.g. "2026-03-14")
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    user: Mapped["User | None"] = relationship(back_populates="consent_records")


class PasswordResetToken(Base):
    """Single-use password reset tokens.

    Tokens are generated as URL-safe random strings and stored hashed.
    They expire after a short TTL and are invalidated after use.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    # SHA-256 hex digest of the raw token (never store the raw token)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class PromptLog(Base):
    """Captured prompt + response for users who have granted prompt_logging consent.

    Only written when BOTH conditions hold:
        1. ``users.prompt_logging_eligible`` is True (admin granted)
        2. The user has an active ConsentRecord(consent_type='prompt_logging', granted=True)
           that has not been revoked by a subsequent granted=False record.

    ``kind`` distinguishes which pipeline stage produced the prompt
    (e.g. ``cv``, ``cover_letter``, ``review``, ``keywords``).

    Every consented call is logged regardless of outcome: ``status`` records
    whether the call succeeded or failed and ``error_message`` carries the
    failure detail when relevant, so timeouts and API errors stay visible
    alongside successful prompts.
    """
    __tablename__ = "prompt_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attempt_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True, index=True)

    service: Mapped[str] = mapped_column(String(50), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="cv")
    model: Mapped[str] = mapped_column(String(100), default="")

    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, default="")

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class APIRequestLog(Base):
    """Log of every LLM API call for cost tracking and debugging."""
    __tablename__ = "api_request_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # UUID4 for grouping related calls
    attempt_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)  # links to CV generation attempt
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True, index=True)

    # Request info
    service: Mapped[str] = mapped_column(String(50), nullable=False)  # "ai_generator", "keyword_extractor", etc.
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0)

    # Response info
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="success")  # success, error, timeout
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class FeatureFlag(Base):
    """Runtime feature toggle, editable from /admin/features.

    Presence of a row overrides the registry default for ``key``; absence
    means the registry default applies (often env-driven).
    """
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
