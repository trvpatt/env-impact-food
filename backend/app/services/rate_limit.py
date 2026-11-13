from datetime import timedelta

from sqlmodel import Session, delete, func, select

from app.core.errors import ApiError
from app.models import RateLimitHit
from app.models.base import utcnow


def enforce(session: Session, key: str, limit: int, window_seconds: int) -> None:
    """Record a hit for `key`; raise 429 if more than `limit` hits fall inside the window.

    Stored in the database so the limit holds across every API process.
    """
    window_start = utcnow() - timedelta(seconds=window_seconds)
    session.exec(
        delete(RateLimitHit).where(RateLimitHit.key == key, RateLimitHit.created_at < window_start)
    )
    count = session.exec(
        select(func.count()).select_from(RateLimitHit).where(RateLimitHit.key == key)
    ).one()
    if count >= limit:
        session.commit()
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many requests. Please try again later.",
            headers={"Retry-After": str(window_seconds)},
        )
    session.add(RateLimitHit(key=key))
    session.commit()
