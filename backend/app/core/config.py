from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment-specific values. Loaded from env vars (and `.env` in development)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./rooted.db"

    # Auth
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30
    login_challenge_ttl_seconds: int = 300
    email_token_ttl_minutes: int = 60
    cookie_secure: bool = True

    # Comma-separated list of allowed browser origins.
    cors_origins: str = ""
    # Base URL used to build links in emails (e.g. https://app.example.com).
    frontend_url: str = "http://localhost:5173"

    # Email (SMTP). Use a local catcher such as Mailpit in development.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    email_from: str = "Rooted <no-reply@localhost>"

    # CAPTCHA (hCaptcha / Turnstile / reCAPTCHA share the same verify contract).
    captcha_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    captcha_secret: SecretStr | None = None

    # Payments (Stripe).
    stripe_api_url: str = "https://api.stripe.com/v1"
    stripe_secret_key: SecretStr | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: SecretStr | None = None
    # `plan_id=provider_price_id` pairs, comma-separated. Read by the seed script.
    plan_price_ids: str = ""

    # AI assistant (Anthropic).
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-opus-5"
    llm_max_tokens: int = 16000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
