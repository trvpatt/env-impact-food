import logging
from typing import Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CaptchaVerifier(Protocol):
    def verify(self, token: str, remote_ip: str | None) -> bool: ...


class HttpCaptchaVerifier:
    """hCaptcha, Turnstile and reCAPTCHA all accept `secret` + `response` and return `success`."""

    def verify(self, token: str, remote_ip: str | None) -> bool:
        settings = get_settings()
        if settings.captcha_secret is None:
            logger.error("CAPTCHA_SECRET is not configured; rejecting CAPTCHA")
            return False
        data = {"secret": settings.captcha_secret.get_secret_value(), "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip
        try:
            response = httpx.post(settings.captcha_verify_url, data=data, timeout=10)
            response.raise_for_status()
            return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            logger.exception("CAPTCHA verification request failed")
            return False


def get_captcha_verifier() -> CaptchaVerifier:
    return HttpCaptchaVerifier()
