from dataclasses import dataclass

from sqlmodel import Session

from app.core.errors import ApiError, field_error, unauthorized, validation_error
from app.core.security import hash_password, verify_password
from app.models import EmailTokenPurpose, User
from app.models.base import utcnow
from app.schemas import generated as api
from app.services import rate_limit
from app.services.captcha import CaptchaVerifier
from app.services.email import EmailSender, link
from app.services.tokens import (
    consume_email_token,
    find_login_challenge,
    find_refresh_token,
    issue_email_token,
    issue_login_challenge,
    issue_session,
    revoke_all_refresh_tokens,
)
from app.services.users import (
    birthday_errors,
    find_by_email,
    password_errors,
)

MAX_FAILED_LOGINS = 3


@dataclass
class SignedIn:
    user: User
    access_token: str
    refresh_token: str


def _send_verification(email_sender: EmailSender, user: User, token: str) -> None:
    email_sender.send(
        user.email,
        "Please confirm your email address",
        f"Welcome to Rooted, {user.first_name}! Confirm your email: {link('verify-email', token)}",
    )


def signup(
    session: Session, body: api.SignupRequest, email_sender: EmailSender, client_ip: str
) -> User:
    rate_limit.enforce(session, f"signup:{client_ip}", limit=10, window_seconds=3600)
    password = body.password.root.get_secret_value()
    errors = []
    if find_by_email(session, body.email):
        errors.append(field_error("email", api.Code.EMAIL_IN_USE, "This email is already in use."))
    errors += birthday_errors(body.birthday)
    errors += password_errors(
        password, body.password_confirm.get_secret_value(), "password", "password_confirm"
    )
    if errors:
        raise validation_error(errors)

    user = User(
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        birthday=body.birthday,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.flush()
    token = issue_email_token(session, user, EmailTokenPurpose.VERIFY_EMAIL)
    session.commit()
    session.refresh(user)
    _send_verification(email_sender, user, token)
    return user


def verify_email(session: Session, token: str) -> SignedIn:
    """Confirms a sign-up address or an address change, then signs the user in."""
    row = consume_email_token(
        session, token, {EmailTokenPurpose.VERIFY_EMAIL, EmailTokenPurpose.CHANGE_EMAIL}
    )
    user = session.get(User, row.user_id)
    if row.purpose == EmailTokenPurpose.CHANGE_EMAIL:
        if row.new_email is None or user.pending_email != row.new_email:
            raise ApiError(400, "INVALID_TOKEN", "This link is invalid or has expired.")
        if find_by_email(session, row.new_email):
            raise ApiError(400, "EMAIL_IN_USE", "This email is already in use.")
        user.email, user.pending_email = row.new_email, None
    user.email_verified = True
    user.updated_at = utcnow()
    session.add(user)
    return SignedIn(user, *issue_session(session, user))


def resend_verification(session: Session, email: str, email_sender: EmailSender) -> None:
    rate_limit.enforce(session, f"resend:{email.lower()}", limit=3, window_seconds=3600)
    user = find_by_email(session, email)
    if user is None or user.email_verified:
        return
    token = issue_email_token(session, user, EmailTokenPurpose.VERIFY_EMAIL)
    session.commit()
    _send_verification(email_sender, user, token)


def _lock_and_notify(session: Session, user: User, email_sender: EmailSender) -> ApiError:
    user.login_locked = True
    token = issue_email_token(session, user, EmailTokenPurpose.LOGIN_UNLOCK)
    session.add(user)
    session.commit()
    email_sender.send(
        user.email,
        "Confirm it's you signing in",
        "We noticed several failed sign-in attempts on your Rooted account. "
        f"If this was you, confirm here to sign in: {link('login/confirm', token)}",
    )
    return _locked_error()


def _locked_error() -> ApiError:
    return ApiError(
        423,
        "EMAIL_CONFIRMATION_REQUIRED",
        "Too many failed attempts. We emailed you a link to confirm it's you.",
    )


def login(
    session: Session, body: api.LoginRequest, email_sender: EmailSender, client_ip: str
) -> api.LoginChallenge:
    rate_limit.enforce(session, f"login:{client_ip}", limit=20, window_seconds=900)
    user = find_by_email(session, body.email)
    if user is None:
        raise ApiError(
            401,
            "INVALID_CREDENTIALS",
            "Incorrect email or password.",
            extra={"attempts_remaining": MAX_FAILED_LOGINS - 1},
        )
    if user.login_locked:
        raise _locked_error()
    if not verify_password(body.password.get_secret_value(), user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            raise _lock_and_notify(session, user, email_sender)
        session.add(user)
        session.commit()
        raise ApiError(
            401,
            "INVALID_CREDENTIALS",
            "Incorrect email or password.",
            extra={"attempts_remaining": MAX_FAILED_LOGINS - user.failed_login_attempts},
        )
    if not user.email_verified:
        raise ApiError(403, "EMAIL_NOT_VERIFIED", "Please confirm your email address first.")
    user.failed_login_attempts = 0
    session.add(user)
    challenge_id, challenge = issue_login_challenge(session, user)
    return api.LoginChallenge(challenge_id=challenge_id, expires_at=challenge.expires_at)


def complete_login_captcha(
    session: Session, body: api.CaptchaRequest, captcha: CaptchaVerifier, client_ip: str
) -> SignedIn:
    challenge = find_login_challenge(session, body.challenge_id)
    if challenge is None or challenge.used_at or challenge.expires_at < utcnow():
        raise ApiError(400, "CHALLENGE_EXPIRED", "Your sign-in expired. Please sign in again.")
    if not captcha.verify(body.captcha_token, client_ip):
        raise ApiError(400, "CAPTCHA_FAILED", "CAPTCHA verification failed. Please try again.")
    challenge.used_at = utcnow()
    session.add(challenge)
    user = session.get(User, challenge.user_id)
    return SignedIn(user, *issue_session(session, user))


def confirm_login_from_email(session: Session, token: str) -> SignedIn:
    row = consume_email_token(session, token, {EmailTokenPurpose.LOGIN_UNLOCK})
    user = session.get(User, row.user_id)
    user.login_locked = False
    user.failed_login_attempts = 0
    user.email_verified = True  # Clicking the link proves ownership of the address.
    session.add(user)
    return SignedIn(user, *issue_session(session, user))


def refresh(session: Session, refresh_token: str | None) -> SignedIn:
    if not refresh_token:
        raise unauthorized()
    row = find_refresh_token(session, refresh_token)
    if row is None:
        raise unauthorized()
    if row.revoked_at is not None:
        # A rotated token was replayed: assume theft and end every session for this user.
        revoke_all_refresh_tokens(session, row.user_id)
        session.commit()
        raise unauthorized()
    if row.expires_at < utcnow():
        raise unauthorized()
    row.revoked_at = utcnow()
    session.add(row)
    user = session.get(User, row.user_id)
    return SignedIn(user, *issue_session(session, user))


def logout(session: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    row = find_refresh_token(session, refresh_token)
    if row and row.revoked_at is None:
        row.revoked_at = utcnow()
        session.add(row)
        session.commit()


def forgot_password(session: Session, email: str, email_sender: EmailSender) -> None:
    rate_limit.enforce(session, f"forgot:{email.lower()}", limit=3, window_seconds=3600)
    user = find_by_email(session, email)
    if user is None:
        return
    token = issue_email_token(session, user, EmailTokenPurpose.PASSWORD_RESET)
    session.commit()
    email_sender.send(
        user.email,
        "Reset your Rooted password",
        f"Reset your password here: {link('reset-password', token)}\n"
        "If you didn't ask for this, you can ignore this email.",
    )


def reset_password(session: Session, body: api.ResetPasswordRequest) -> None:
    password = body.password.root.get_secret_value()
    errors = password_errors(
        password, body.password_confirm.get_secret_value(), "password", "password_confirm"
    )
    if errors:
        raise validation_error(errors)
    row = consume_email_token(session, body.token, {EmailTokenPurpose.PASSWORD_RESET})
    user = session.get(User, row.user_id)
    user.password_hash = hash_password(password)
    user.token_version += 1
    user.login_locked = False
    user.failed_login_attempts = 0
    user.updated_at = utcnow()
    session.add(user)
    revoke_all_refresh_tokens(session, user.id)
    session.commit()
