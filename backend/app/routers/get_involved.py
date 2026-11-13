from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import CursorParam, LimitParam
from app.routers.restaurants import PostalCodeParam
from app.schemas import generated as api
from app.services import places

router = APIRouter(tags=["Get Involved"])


@router.get("/community/search", response_model=api.CommunityOrgPage)
def search_community_opportunities(
    types: Annotated[
        str, Query(description="Comma-separated: food_pantry, soup_kitchen, community_garden.")
    ],
    user: CurrentUser,
    session: SessionDep,
    postal_code: PostalCodeParam = None,
    radius_miles: api.RadiusMiles = api.RadiusMiles.integer_10,
    cursor: CursorParam = None,
    limit: LimitParam = 20,
):
    parsed = places.parse_types(types, api.CommunityOrgType)
    center = places.resolve_center(session, None, None, postal_code, user)
    return places.search_community(session, center, radius_miles.value, parsed, cursor, limit)
