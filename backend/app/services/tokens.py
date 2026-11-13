"""Single-use email tokens, refresh tokens and login challenges. Only hashes are stored."""

from datetime import timedelta
from uuid import UUID

from sqlmodel import Session, select, update

from app.core.config import get_settings
from app.core.errors import invalid_token
from app.core.security import create_access_token, hash_token, new_opaque_token
from app.models import EmailToken, LoginChallenge, RefreshToken, User
from app.models.base import utcnow


def issue_email_token(
    session: Session, user: User, purpose: str, new_email: str | None = None
) -> str:
    """Create a token for `purpose`, invalidating earlier unused ones. Caller commits."""
    now = utcnow()
    session.exec(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    token = new_opaque_token()
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token),
            new_email=new_email,
            expires_at=now + timedelta(minutes=get_settings().email_token_ttl_minutes),
        )
    )
    return token


def consume_email_token(session: Session, token: str, purposes: set[str]) -> EmailToken:
    """Mark a valid token used and return it, or raise 400 INVALID_TOKEN. Caller commits."""
    row = session.exec(select(EmailToken).where(EmailToken.token_hash == hash_token(token))).first()
    if row is None or row.purpose not in purposes or row.used_at or row.expires_at < utcnow():
        raise invalid_token()
    row.used_at = utcnow()
    session.add(row)
    return row


def issue_session(session: Session, user: User) -> tuple[str, str]:
    """Return `(access_token, refresh_token)` and persist the refresh token hash. Commits."""
    refresh = new_opaque_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=utcnow() + timedelta(days=get_settings().refresh_token_ttl_days),
        )
    )
    session.commit()
    return create_access_token(user.id, user.token_version), refresh


def revoke_all_refresh_tokens(session: Session, user_id: UUID) -> None:
    session.exec(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def find_refresh_token(session: Session, token: str) -> RefreshToken | None:
    return session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
    ).first()


def issue_login_challenge(session: Session, user: User) -> tuple[str, LoginChallenge]:
    challenge_id = new_opaque_token()
    challenge = LoginChallenge(
        user_id=user.id,
        token_hash=hash_token(challenge_id),
        expires_at=utcnow() + timedelta(seconds=get_settings().login_challenge_ttl_seconds),
    )
    session.add(challenge)
    session.commit()
    session.refresh(challenge)
    return challenge_id, challenge


def find_login_challenge(session: Session, challenge_id: str) -> LoginChallenge | None:
    return session.exec(
        select(LoginChallenge).where(LoginChallenge.token_hash == hash_token(challenge_id))
    ).first()
