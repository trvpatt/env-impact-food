import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, select

from app.core.errors import ApiError, field_error, not_found, validation_error
from app.models import PaymentMethod, Plan, Subscription, User
from app.models.base import utcnow
from app.schemas import generated as api
from app.services.payments import PaymentProviderError, StripeClient

logger = logging.getLogger(__name__)

LOCAL_PREFIX = "local_"


def _plan_schema(plan: Plan) -> api.Plan:
    return api.Plan.model_validate(plan, from_attributes=True)


def list_plans(session: Session) -> list[api.Plan]:
    rows = session.exec(
        select(Plan)
        .where(Plan.active == True)
        .order_by(Plan.sort_order, Plan.price_cents)  # noqa: E712
    ).all()
    return [_plan_schema(p) for p in rows]


def to_subscription_schema(session: Session, sub: Subscription) -> api.Subscription:
    return api.Subscription(
        id=sub.id,
        plan=_plan_schema(session.get(Plan, sub.plan_id)),
        status=sub.status,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


def get_subscription(session: Session, user: User) -> Subscription:
    sub = session.exec(select(Subscription).where(Subscription.user_id == user.id)).first()
    if sub is None:
        raise not_found("No subscription.")
    return sub


def _provider_error(exc: PaymentProviderError) -> ApiError:
    if exc.status_code == 402:
        return ApiError(402, "PAYMENT_REQUIRED", str(exc))
    logger.error("Payment provider error (%s): %s", exc.status_code, exc)
    return ApiError(502, "PAYMENT_PROVIDER_ERROR", "Payment provider error. Please try again.")


def _ensure_customer(session: Session, user: User, client: StripeClient) -> str:
    if user.payment_customer_id is None:
        user.payment_customer_id = client.create_customer(user.email, str(user.id))
        session.add(user)
        session.commit()
    return user.payment_customer_id


def _apply_provider_subscription(session: Session, user_id, data: dict, plan_id: str | None = None):
    """Upsert our row from a provider subscription object."""
    sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    if plan_id is None:
        price_id = data["items"]["data"][0]["price"]["id"]
        plan = session.exec(select(Plan).where(Plan.provider_price_id == price_id)).first()
        if plan is None:
            logger.warning("Subscription %s references unknown price %s", data["id"], price_id)
            return None
        plan_id = plan.id
    if sub is not None and sub.id != data["id"]:
        session.delete(sub)
        session.flush()
        sub = None
    sub = sub or Subscription(
        id=data["id"], user_id=user_id, plan_id=plan_id, status=data["status"]
    )
    period_end = data.get("current_period_end") or (
        data.get("items", {}).get("data", [{}])[0].get("current_period_end")
    )
    sub.plan_id = plan_id
    sub.status = data["status"]
    sub.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    sub.current_period_end = datetime.fromtimestamp(period_end, UTC) if period_end else None
    sub.updated_at = utcnow()
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def create_subscription(session: Session, user: User, plan_id: str, get_client) -> Subscription:
    plan = session.get(Plan, plan_id)
    if plan is None or not plan.active:
        raise validation_error([field_error("plan_id", api.Code.INVALID_VALUE, "Unknown plan.")])
    existing = session.exec(select(Subscription).where(Subscription.user_id == user.id)).first()

    if plan.price_cents == 0 or plan.provider_price_id is None:
        if existing and not existing.id.startswith(LOCAL_PREFIX) and existing.status != "canceled":
            raise ApiError(
                409, "SUBSCRIPTION_ACTIVE", "Cancel your paid plan before switching to a free plan."
            )
        if existing:
            session.delete(existing)
            session.flush()
        sub = Subscription(
            id=f"{LOCAL_PREFIX}{uuid4().hex}", user_id=user.id, plan_id=plan.id, status="active"
        )
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return sub

    if session.get(PaymentMethod, user.id) is None:
        raise ApiError(402, "PAYMENT_REQUIRED", "Please add a payment method first.")
    client: StripeClient = get_client()
    try:
        customer_id = _ensure_customer(session, user, client)
        if existing and not existing.id.startswith(LOCAL_PREFIX) and existing.status != "canceled":
            data = client.change_subscription_price(existing.id, plan.provider_price_id)
        else:
            data = client.create_subscription(customer_id, plan.provider_price_id)
    except PaymentProviderError as exc:
        raise _provider_error(exc)
    return _apply_provider_subscription(session, user.id, data, plan_id=plan.id)


def cancel_subscription(session: Session, user: User, get_client) -> Subscription:
    sub = get_subscription(session, user)
    if sub.id.startswith(LOCAL_PREFIX):
        sub.status = "canceled"
        sub.updated_at = utcnow()
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return sub
    try:
        data = get_client().cancel_subscription_at_period_end(sub.id)
    except PaymentProviderError as exc:
        raise _provider_error(exc)
    return _apply_provider_subscription(session, user.id, data, plan_id=sub.plan_id)


def create_payment_method_setup(
    session: Session, user: User, client: StripeClient
) -> api.PaymentSetup:
    try:
        customer_id = _ensure_customer(session, user, client)
        client_secret = client.create_setup_intent(customer_id)
    except PaymentProviderError as exc:
        raise _provider_error(exc)
    return api.PaymentSetup(client_secret=client_secret, publishable_key=client.publishable_key)


def get_payment_method(session: Session, user: User) -> api.PaymentMethodSummary:
    pm = session.get(PaymentMethod, user.id)
    if pm is None:
        raise not_found("No payment method on file.")
    return api.PaymentMethodSummary(
        brand=pm.brand,
        last4=pm.last4,
        exp_month=pm.exp_month,
        exp_year=pm.exp_year,
        billing_address=pm.billing_address,
    )


def _user_for_customer(session: Session, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    return session.exec(select(User).where(User.payment_customer_id == customer_id)).first()


def _billing_address(details: dict) -> dict | None:
    addr = (details or {}).get("address") or {}
    if not addr.get("line1"):
        return None
    return {
        "line1": addr["line1"],
        "line2": addr.get("line2"),
        "city": addr.get("city") or "",
        "state": addr.get("state") or "",
        "postal_code": addr.get("postal_code") or "",
        "country": addr.get("country") or "US",
    }


def handle_webhook_event(session: Session, event: dict, get_client) -> None:
    kind = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    user = _user_for_customer(session, obj.get("customer"))
    if user is None:
        logger.info("Ignoring %s webhook for unknown customer", kind)
        return

    if kind == "setup_intent.succeeded":
        client: StripeClient = get_client()
        try:
            pm = client.get_payment_method(obj["payment_method"])
            client.set_default_payment_method(user.payment_customer_id, pm["id"])
        except PaymentProviderError as exc:
            raise _provider_error(exc)
        card = pm.get("card", {})
        row = session.get(PaymentMethod, user.id) or PaymentMethod(
            user_id=user.id,
            provider_payment_method_id=pm["id"],
            brand=card.get("brand", "unknown"),
            last4=card.get("last4", "0000"),
            exp_month=card.get("exp_month", 1),
            exp_year=card.get("exp_year", 1970),
        )
        row.provider_payment_method_id = pm["id"]
        row.brand = card.get("brand", row.brand)
        row.last4 = card.get("last4", row.last4)
        row.exp_month = card.get("exp_month", row.exp_month)
        row.exp_year = card.get("exp_year", row.exp_year)
        row.billing_address = _billing_address(pm.get("billing_details"))
        row.updated_at = utcnow()
        session.add(row)
        session.commit()
    elif kind in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        _apply_provider_subscription(session, user.id, obj)
