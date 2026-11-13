from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import CursorParam, LimitParam
from app.routers.restaurants import PostalCodeParam
from app.schemas import generated as api
from app.services import places

router = APIRouter(tags=["Local Produce"])


@router.get("/local-food/search", response_model=api.LocalFoodPage)
def search_local_food(
    types: Annotated[
        str, Query(description="Comma-separated: farmers_market, coop, local_grocer.")
    ],
    user: CurrentUser,
    session: SessionDep,
    postal_code: PostalCodeParam = None,
    radius_miles: api.RadiusMiles = api.RadiusMiles.integer_10,
    cursor: CursorParam = None,
    limit: LimitParam = 20,
):
    parsed = places.parse_types(types, api.LocalFoodType)
    center = places.resolve_center(session, None, None, postal_code, user)
    return places.search_local_food(session, center, radius_miles.value, parsed, cursor, limit)
