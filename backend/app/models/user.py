from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, utcnow


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(max_length=254, unique=True, index=True)
    pending_email: str | None = Field(default=None, max_length=254)
    email_verified: bool = False
    password_hash: str
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    birthday: date
    address: dict | None = Field(default=None, sa_type=JSON)
    avatar_id: str | None = Field(default=None, foreign_key="avatars.id")
    onboarding_completed: bool = False
    failed_login_attempts: int = 0
    login_locked: bool = False
    # Bumped on password reset to invalidate outstanding access tokens.
    token_version: int = 0
    payment_customer_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class Survey(SQLModel, table=True):
    __tablename__ = "surveys"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    diet: str | None = None
    cuisine_ids: list[str] | None = Field(default=None, sa_type=JSON)
    health_goals: list[str] | None = Field(default=None, sa_type=JSON)
    motivations: list[str] | None = Field(default=None, sa_type=JSON)
    income_band: str | None = None
    completed_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class EmailTokenPurpose:
    VERIFY_EMAIL = "verify_email"
    CHANGE_EMAIL = "change_email"
    LOGIN_UNLOCK = "login_unlock"
    PASSWORD_RESET = "password_reset"


class EmailToken(SQLModel, table=True):
    """Single-use token sent in an email link. Only the hash is stored."""

    __tablename__ = "email_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    purpose: str = Field(max_length=32)
    token_hash: str = Field(unique=True, index=True)
    new_email: str | None = None
    expires_at: datetime = Field(sa_type=UTCDateTime)
    used_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_type=UTCDateTime)
    revoked_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class LoginChallenge(SQLModel, table=True):
    """Ties the CAPTCHA step to a successful password check."""

    __tablename__ = "login_challenges"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_type=UTCDateTime)
    used_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class RateLimitHit(SQLModel, table=True):
    """Shared rate-limit counter so limits hold across processes."""

    __tablename__ = "rate_limit_hits"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(max_length=200, index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, index=True)
