"""SQLAlchemy models for users, credits, payments, and WebAuthn credentials."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    credits: Mapped[list["Credit"]] = relationship(back_populates="user", lazy="selectin")
    webauthn_credentials: Mapped[list["WebAuthnCredential"]] = relationship(back_populates="user", lazy="selectin")


class Credit(Base):
    __tablename__ = "credits"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    total_purchased: Mapped[int] = mapped_column(Integer, default=0)
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
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "ai" or "builder"
    label: Mapped[str] = mapped_column(String(255), default="")  # user-chosen name for this CV
    job_title: Mapped[str] = mapped_column(String(255), default="")  # target job title (optional)
    region: Mapped[str] = mapped_column(String(5), nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)  # sanitized markdown content
    cv_data_json: Mapped[str] = mapped_column(Text, nullable=False)  # structured CV data as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


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
