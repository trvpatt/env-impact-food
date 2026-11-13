"""Payment provider client (Stripe REST API). Card data never passes through this service."""

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ApiError

logger = logging.getLogger(__name__)

WEBHOOK_TOLERANCE_SECONDS = 300


class PaymentProviderError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class StripeClient:
    def __init__(self, api_url: str, secret_key: str, publishable_key: str):
        self.api_url = api_url.rstrip("/")
        self.secret_key = secret_key
        self.publishable_key = publishable_key

    def _request(self, method: str, path: str, data: dict | None = None) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                f"{self.api_url}{path}",
                data=data,
                auth=(self.secret_key, ""),
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise PaymentProviderError(503, "Payment provider unreachable") from exc
        body = response.json() if response.content else {}
        if response.is_error:
            message = body.get("error", {}).get("message", "Payment provider error")
            raise PaymentProviderError(response.status_code, message)
        return body

    def create_customer(self, email: str, user_id: str) -> str:
        return self._request("POST", "/customers", {"email": email, "metadata[user_id]": user_id})[
            "id"
        ]

    def create_setup_intent(self, customer_id: str) -> str:
        body = self._request(
            "POST",
            "/setup_intents",
            {"customer": customer_id, "usage": "off_session", "payment_method_types[]": "card"},
        )
        return body["client_secret"]

    def get_payment_method(self, payment_method_id: str) -> dict:
        return self._request("GET", f"/payment_methods/{payment_method_id}")

    def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> None:
        self._request(
            "POST",
            f"/customers/{customer_id}",
            {"invoice_settings[default_payment_method]": payment_method_id},
        )

    def create_subscription(self, customer_id: str, price_id: str) -> dict:
        return self._request(
            "POST",
            "/subscriptions",
            {
                "customer": customer_id,
                "items[0][price]": price_id,
                "payment_behavior": "error_if_incomplete",
            },
        )

    def get_subscription(self, subscription_id: str) -> dict:
        return self._request("GET", f"/subscriptions/{subscription_id}")

    def change_subscription_price(self, subscription_id: str, price_id: str) -> dict:
        item_id = self.get_subscription(subscription_id)["items"]["data"][0]["id"]
        return self._request(
            "POST",
            f"/subscriptions/{subscription_id}",
            {
                "items[0][id]": item_id,
                "items[0][price]": price_id,
                "cancel_at_period_end": "false",
                "payment_behavior": "error_if_incomplete",
            },
        )

    def cancel_subscription_at_period_end(self, subscription_id: str) -> dict:
        return self._request(
            "POST", f"/subscriptions/{subscription_id}", {"cancel_at_period_end": "true"}
        )


def get_payment_client() -> StripeClient:
    settings = get_settings()
    if settings.stripe_secret_key is None or settings.stripe_publishable_key is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Payments are not configured.")
    return StripeClient(
        settings.stripe_api_url,
        settings.stripe_secret_key.get_secret_value(),
        settings.stripe_publishable_key,
    )


def verify_webhook(payload: bytes, signature_header: str | None) -> dict:
    """Verify a Stripe `Stripe-Signature` header and return the parsed event."""
    settings = get_settings()
    if settings.stripe_webhook_secret is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Payments are not configured.")
    invalid = ApiError(400, "INVALID_SIGNATURE", "Invalid webhook signature.")
    if not signature_header:
        raise invalid
    parts: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        key, _, value = item.partition("=")
        parts.setdefault(key.strip(), []).append(value.strip())
    try:
        timestamp = int(parts["t"][0])
    except (KeyError, ValueError):
        raise invalid
    if abs(time.time() - timestamp) > WEBHOOK_TOLERANCE_SECONDS:
        raise invalid
    expected = hmac.new(
        settings.stripe_webhook_secret.get_secret_value().encode(),
        f"{timestamp}.".encode() + payload,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in parts.get("v1", [])):
        raise invalid
    try:
        return json.loads(payload)
    except ValueError:
        raise invalid
