import base64
import json
from typing import Annotated, TypeVar

from fastapi import Query
from sqlmodel import Session

from app.core.errors import field_error, validation_error
from app.schemas.generated import Code

T = TypeVar("T")

CursorParam = Annotated[str | None, Query(description="Opaque cursor from `next_cursor`.")]
LimitParam = Annotated[int, Query(ge=1, le=100)]


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        offset = int(json.loads(base64.urlsafe_b64decode(cursor.encode()))["o"])
    except (ValueError, KeyError, TypeError):
        offset = -1
    if offset < 0:
        raise validation_error([field_error("cursor", Code.INVALID_FORMAT, "Invalid cursor.")])
    return offset


def paginate_query(session: Session, statement, cursor: str | None, limit: int):
    """Run an ordered select and return `(rows, next_cursor)`."""
    offset = decode_cursor(cursor)
    rows = list(session.exec(statement.offset(offset).limit(limit + 1)).all())
    next_cursor = encode_cursor(offset + limit) if len(rows) > limit else None
    return rows[:limit], next_cursor


def paginate_list(items: list[T], cursor: str | None, limit: int) -> tuple[list[T], str | None]:
    """Paginate an already-filtered, already-sorted in-memory list."""
    offset = decode_cursor(cursor)
    page = items[offset : offset + limit]
    next_cursor = encode_cursor(offset + limit) if offset + limit < len(items) else None
    return page, next_cursor


def split_csv(value: str | None) -> list[str]:
    """Parse a `style: form, explode: false` array query param (`a,b,c`)."""
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]
