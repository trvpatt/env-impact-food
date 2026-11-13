from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import LimitParam
from app.schemas import generated as api
from app.services import foods as service

router = APIRouter(prefix="/foods", tags=["Foods"])


@router.get("", response_model=list[api.FoodSummary])
def search_foods(
    q: Annotated[str, Query(min_length=2, max_length=100)],
    _: CurrentUser,
    session: SessionDep,
    limit: LimitParam = 20,
):
    return service.search(session, q, limit)


@router.get("/{food_id}", response_model=api.FoodDetail)
def get_food(food_id: str, _: CurrentUser, session: SessionDep):
    return service.get(session, food_id)
