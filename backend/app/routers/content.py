from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import CursorParam, LimitParam
from app.schemas import generated as api
from app.services import content as service

router = APIRouter(tags=["Content"])


@router.get("/articles", response_model=api.ArticlePage)
def list_articles(
    _: CurrentUser,
    session: SessionDep,
    topic: str | None = None,
    cursor: CursorParam = None,
    limit: LimitParam = 20,
):
    return service.list_articles(session, topic, cursor, limit)
