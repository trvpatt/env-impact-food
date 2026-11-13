import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.generated import Code, Error, FieldError

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised anywhere in the app; rendered as the spec's `Error` shape."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        field_errors: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field_errors = field_errors
        self.headers = headers
        self.extra = extra or {}


def field_error(field: str, code: Code, message: str) -> FieldError:
    return FieldError(field=field, code=code, message=message)


def validation_error(field_errors: list[FieldError]) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Please correct invalid fields", field_errors)


def not_found(message: str = "Resource not found") -> ApiError:
    return ApiError(404, "NOT_FOUND", message)


def unauthorized(message: str = "Authentication required") -> ApiError:
    return ApiError(401, "UNAUTHORIZED", message)


def invalid_token() -> ApiError:
    return ApiError(400, "INVALID_TOKEN", "This link is invalid or has expired.")


def _error_body(code: str, message: str, field_errors=None, **extra) -> dict:
    body = Error(code=code, message=message, field_errors=field_errors).model_dump(
        mode="json", exclude_none=True
    )
    body.update(extra)
    return body


_PYDANTIC_CODE_MAP = {
    "missing": Code.REQUIRED,
    "enum": Code.INVALID_VALUE,
    "literal_error": Code.INVALID_VALUE,
    "greater_than": Code.OUT_OF_RANGE,
    "greater_than_equal": Code.OUT_OF_RANGE,
    "less_than": Code.OUT_OF_RANGE,
    "less_than_equal": Code.OUT_OF_RANGE,
    "too_short": Code.OUT_OF_RANGE,
    "too_long": Code.OUT_OF_RANGE,
}


def _to_field_error(err: dict) -> FieldError:
    loc = [
        str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path", "header", "cookie")
    ]
    field = ".".join(loc) or "body"
    code = _PYDANTIC_CODE_MAP.get(err.get("type", ""), Code.INVALID_FORMAT)
    if "email" in err.get("msg", "").lower():
        code = Code.INVALID_EMAIL
    return FieldError(field=field, code=code, message=err.get("msg", "Invalid value"))


_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    429: "RATE_LIMITED",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.field_errors, **exc.extra),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        field_errors = [_to_field_error(e) for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", "Please correct invalid fields", field_errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception):
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "Something went wrong. Please try again."),
        )
