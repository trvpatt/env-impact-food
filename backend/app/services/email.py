import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpEmailSender:
    """Sends mail through the SMTP server named in config (Mailpit locally, a provider in prod)."""

    def send(self, to: str, subject: str, body: str) -> None:
        settings = get_settings()
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            # Log the failure, never the body: it contains single-use tokens.
            logger.exception("Failed to send email %r", subject)


def get_email_sender() -> EmailSender:
    return SmtpEmailSender()


def link(path: str, token: str) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}/{path}?token={token}"
