from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import CursorParam, LimitParam, split_csv
from app.schemas import generated as api
from app.services import places

router = APIRouter(tags=["Restaurants"])

PostalCodeParam = Annotated[str | None, Query(pattern=r"^\d{5}(-\d{4})?$")]
CuisineIdsParam = Annotated[str | None, Query(description="Comma-separated cuisine ids.")]


@router.get("/restaurants/search", response_model=api.RestaurantPage)
def search_restaurants(
    diet: api.Diet,
    user: CurrentUser,
    session: SessionDep,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    postal_code: PostalCodeParam = None,
    radius_miles: api.RadiusMiles = api.RadiusMiles.integer_10,
    cuisine_ids: CuisineIdsParam = None,
):
    center = places.resolve_center(session, lat, lng, postal_code)
    return places.search_restaurants(
        session, user, center, radius_miles.value, diet, split_csv(cuisine_ids)
    )


@router.get("/restaurants/{restaurant_id}", response_model=api.Restaurant)
def get_restaurant(restaurant_id: str, user: CurrentUser, session: SessionDep):
    return places.get_restaurant(session, user, restaurant_id)


@router.get("/users/me/favorites/restaurants", response_model=api.RestaurantPage)
def list_favorite_restaurants(
    user: CurrentUser, session: SessionDep, cursor: CursorParam = None, limit: LimitParam = 20
):
    return places.list_favorite_restaurants(session, user, cursor, limit)


@router.put(
    "/users/me/favorites/restaurants/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT
)
def add_favorite_restaurant(restaurant_id: str, user: CurrentUser, session: SessionDep):
    places.add_favorite_restaurant(session, user, restaurant_id)


@router.delete(
    "/users/me/favorites/restaurants/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_favorite_restaurant(restaurant_id: str, user: CurrentUser, session: SessionDep):
    places.remove_favorite_restaurant(session, user, restaurant_id)
