from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.db import get_session
from app.core.errors import unauthorized
from app.core.security import decode_access_token
from app.models import User

SessionDep = Annotated[Session, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise unauthorized("Your session has expired. Please sign in again.")
    try:
        user = session.get(User, UUID(payload["sub"]))
    except ValueError:
        user = None
    if user is None or payload.get("ver") != user.token_version:
        raise unauthorized("Your session has expired. Please sign in again.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
