import base64
import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings

# scrypt parameters (OWASP minimum: N=2^17, r=8, p=1).
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**17, 8, 1
_SCRYPT_MAXMEM = 256 * 1024 * 1024


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, maxmem=_SCRYPT_MAXMEM, dklen=32
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        actual = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(actual, base64.b64decode(digest))


_PASSWORD_RULES = [r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]"]


def is_strong_password(password: str) -> bool:
    return 12 <= len(password) <= 128 and all(re.search(rule, password) for rule in _PASSWORD_RULES)


def create_access_token(user_id: UUID, token_version: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError:
        return None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Single-use and refresh tokens are stored only as SHA-256 hashes."""
    return hashlib.sha256(token.encode()).hexdigest()
