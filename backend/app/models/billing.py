from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, utcnow


class Plan(SQLModel, table=True):
    __tablename__ = "plans"

    id: str = Field(primary_key=True, max_length=50)
    name: str
    price_cents: int
    currency: str = "usd"
    interval: str  # month | year
    features: list[str] = Field(default_factory=list, sa_type=JSON)
    # Payment provider price id; null for free plans.
    provider_price_id: str | None = None
    active: bool = True
    sort_order: int = 0


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"

    # Provider subscription id, or `local_<uuid>` for free plans.
    id: str = Field(primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", unique=True, ondelete="CASCADE")
    plan_id: str = Field(foreign_key="plans.id")
    status: str
    current_period_end: datetime | None = Field(default=None, sa_type=UTCDateTime)
    cancel_at_period_end: bool = False
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class PaymentMethod(SQLModel, table=True):
    """Card summary reported by the provider webhook. Never holds card numbers."""

    __tablename__ = "payment_methods"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    provider_payment_method_id: str
    brand: str
    last4: str = Field(max_length=4)
    exp_month: int
    exp_year: int
    billing_address: dict | None = Field(default=None, sa_type=JSON)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
