from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas import generated as api
from app.services import users as service
from app.services.email import EmailSender, get_email_sender

router = APIRouter(prefix="/users/me", tags=["Users"])


@router.get("", response_model=api.User)
def get_current_user(user: CurrentUser, session: SessionDep):
    return service.to_user_schema(session, user)


@router.patch("", response_model=api.User)
def update_current_user(
    body: api.UserUpdate,
    user: CurrentUser,
    session: SessionDep,
    email: Annotated[EmailSender, Depends(get_email_sender)],
):
    return service.to_user_schema(session, service.update_user(session, user, body, email))


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: api.ChangePasswordRequest, user: CurrentUser, session: SessionDep):
    service.change_password(session, user, body)
