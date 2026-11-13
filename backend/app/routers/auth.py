from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.schemas import generated as api
from app.services import auth as service
from app.services.captcha import CaptchaVerifier, get_captcha_verifier
from app.services.email import EmailSender, get_email_sender
from app.services.users import to_user_schema

router = APIRouter(prefix="/auth", tags=["Auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

EmailDep = Annotated[EmailSender, Depends(get_email_sender)]
CaptchaDep = Annotated[CaptchaVerifier, Depends(get_captcha_verifier)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _signed_in(session, response: Response, result: service.SignedIn) -> api.AuthTokens:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        result.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return api.AuthTokens(
        access_token=result.access_token,
        token_type="bearer",
        expires_in=settings.access_token_ttl_seconds,
        user=to_user_schema(session, result.user),
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=api.SignupResponse)
def signup(body: api.SignupRequest, request: Request, session: SessionDep, email: EmailDep):
    user = service.signup(session, body, email, _client_ip(request))
    return api.SignupResponse(
        user_id=user.id, email=user.email, message="Please confirm your email address"
    )


@router.post("/verify-email", response_model=api.AuthTokens)
def verify_email(body: api.EmailTokenRequest, response: Response, session: SessionDep):
    return _signed_in(session, response, service.verify_email(session, body.token))


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_verification_email(body: api.EmailRequest, session: SessionDep, email: EmailDep):
    service.resend_verification(session, body.email, email)


@router.post("/login", response_model=api.LoginChallenge)
def login(body: api.LoginRequest, request: Request, session: SessionDep, email: EmailDep):
    return service.login(session, body, email, _client_ip(request))


@router.post("/login/captcha", response_model=api.AuthTokens)
def complete_login_captcha(
    body: api.CaptchaRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    captcha: CaptchaDep,
):
    result = service.complete_login_captcha(session, body, captcha, _client_ip(request))
    return _signed_in(session, response, result)


@router.post("/login/confirm", response_model=api.AuthTokens)
def confirm_login_from_email(body: api.EmailTokenRequest, response: Response, session: SessionDep):
    return _signed_in(session, response, service.confirm_login_from_email(session, body.token))


@router.post("/refresh", response_model=api.AuthTokens)
def refresh_access_token(
    response: Response, session: SessionDep, refresh_token: RefreshCookie = None
):
    return _signed_in(session, response, service.refresh(session, refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, session: SessionDep, refresh_token: RefreshCookie = None):
    service.logout(session, refresh_token)
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
    )


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: api.EmailRequest, session: SessionDep, email: EmailDep):
    service.forgot_password(session, body.email, email)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: api.ResetPasswordRequest, session: SessionDep):
    service.reset_password(session, body)
