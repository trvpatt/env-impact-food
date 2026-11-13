from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from starlette.concurrency import run_in_threadpool

from app.core.deps import CurrentUser, SessionDep
from app.schemas import generated as api
from app.services import billing as service
from app.services.payments import StripeClient, get_payment_client, verify_webhook

router = APIRouter(prefix="/billing", tags=["Billing"])


def get_payment_client_factory():
    """Lets services create the client only when a provider call is actually needed."""
    return get_payment_client


ClientFactory = Annotated[object, Depends(get_payment_client_factory)]


@router.get("/plans", response_model=list[api.Plan])
def list_plans(session: SessionDep):
    return service.list_plans(session)


@router.get("/subscription", response_model=api.Subscription)
def get_subscription(user: CurrentUser, session: SessionDep):
    return service.to_subscription_schema(session, service.get_subscription(session, user))


@router.post("/subscription", response_model=api.Subscription)
def create_subscription(
    body: api.SubscriptionCreate, user: CurrentUser, session: SessionDep, get_client: ClientFactory
):
    sub = service.create_subscription(session, user, body.plan_id, get_client)
    return service.to_subscription_schema(session, sub)


@router.post("/subscription/cancel", response_model=api.Subscription)
def cancel_subscription(user: CurrentUser, session: SessionDep, get_client: ClientFactory):
    return service.to_subscription_schema(
        session, service.cancel_subscription(session, user, get_client)
    )


@router.post("/payment-method/setup", response_model=api.PaymentSetup)
def create_payment_method_setup(
    user: CurrentUser,
    session: SessionDep,
    client: Annotated[StripeClient, Depends(get_payment_client)],
):
    return service.create_payment_method_setup(session, user, client)


@router.get("/payment-method", response_model=api.PaymentMethodSummary)
def get_payment_method(user: CurrentUser, session: SessionDep):
    return service.get_payment_method(session, user)


@router.post("/webhook")
async def payment_provider_webhook(
    request: Request,
    session: SessionDep,
    get_client: ClientFactory,
    stripe_signature: Annotated[str | None, Header()] = None,
):
    event = verify_webhook(await request.body(), stripe_signature)
    await run_in_threadpool(service.handle_webhook_event, session, event, get_client)
    return {"received": True}
