from math import asin, cos, radians, sin, sqrt

from sqlmodel import Session, col, select

from app.core.errors import ApiError, field_error, not_found, validation_error
from app.core.pagination import paginate_list, split_csv
from app.models import (
    CommunityOrg,
    FavoriteRestaurant,
    LocalFoodPlace,
    PostalCode,
    Restaurant,
    User,
)
from app.models.base import utcnow
from app.models.place import PlaceBase
from app.schemas import generated as api

EARTH_RADIUS_MILES = 3958.8
MAX_RESTAURANT_RESULTS = 100


def distance_miles(a: api.GeoPoint, lat: float, lng: float) -> float:
    dlat, dlng = radians(lat - a.lat), radians(lng - a.lng)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(lat)) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(h))


def resolve_center(
    session: Session,
    lat: float | None,
    lng: float | None,
    postal_code: str | None,
    user: User | None = None,
) -> api.GeoPoint:
    """Browser coordinates win; then `postal_code`; then (if given) the user's saved address."""
    if lat is not None and lng is not None:
        return api.GeoPoint(lat=lat, lng=lng)
    if lat is not None or lng is not None:
        raise ApiError(400, "LOCATION_REQUIRED", "Provide both latitude and longitude.")
    if postal_code is None and user is not None and user.address:
        postal_code = user.address.get("postal_code")
    if not postal_code:
        raise ApiError(400, "LOCATION_REQUIRED", "Share your location or enter a ZIP code.")
    row = session.get(PostalCode, postal_code[:5])
    if row is None:
        raise ApiError(400, "UNKNOWN_POSTAL_CODE", "We don't recognise that ZIP code.")
    return api.GeoPoint(lat=row.lat, lng=row.lng)


def _within(session: Session, model: type[PlaceBase], center: api.GeoPoint, radius: float, *where):
    """Rows within `radius` miles, nearest first, as `(row, distance)`. Bounding box in SQL, exact in Python."""
    dlat = radius / 69.0
    dlng = radius / max(69.0 * cos(radians(center.lat)), 0.01)
    statement = select(model).where(
        col(model.lat).between(center.lat - dlat, center.lat + dlat),
        col(model.lng).between(center.lng - dlng, center.lng + dlng),
        *where,
    )
    results = []
    for row in session.exec(statement).all():
        d = distance_miles(center, row.lat, row.lng)
        if d <= radius:
            results.append((row, round(d, 2)))
    results.sort(key=lambda pair: pair[1])
    return results


def _place_fields(row: PlaceBase, distance: float | None) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "address": row.address,
        "location": {"lat": row.lat, "lng": row.lng},
        "hours": row.hours,
        "contact": row.contact,
        "distance_miles": distance if distance is not None else 0.0,
        "image_url": row.image_url,
    }


def _favorite_restaurant_ids(session: Session, user: User) -> set[str]:
    return set(
        session.exec(
            select(FavoriteRestaurant.restaurant_id).where(FavoriteRestaurant.user_id == user.id)
        ).all()
    )


def _restaurant_schema(row: Restaurant, distance: float | None, favorite: bool) -> api.Restaurant:
    return api.Restaurant(
        **_place_fields(row, distance),
        cuisine_ids=row.cuisine_ids,
        diets_supported=row.diets_supported,
        price_level=row.price_level,
        rating=row.rating,
        is_favorite=favorite,
    )


def search_restaurants(
    session: Session,
    user: User,
    center: api.GeoPoint,
    radius: int,
    diet: api.Diet,
    cuisine_ids: list[str],
) -> api.RestaurantPage:
    favorites = _favorite_restaurant_ids(session, user)
    items = []
    for row, d in _within(session, Restaurant, center, radius):
        if diet.value not in row.diets_supported:
            continue
        if cuisine_ids and not set(cuisine_ids) & set(row.cuisine_ids):
            continue
        items.append(_restaurant_schema(row, d, row.id in favorites))
        if len(items) == MAX_RESTAURANT_RESULTS:
            break
    return api.RestaurantPage(items=items, next_cursor=None, search_center=center)


def get_restaurant(session: Session, user: User, restaurant_id: str) -> api.Restaurant:
    row = session.get(Restaurant, restaurant_id)
    if row is None:
        raise not_found("Restaurant not found.")
    return _restaurant_schema(row, None, restaurant_id in _favorite_restaurant_ids(session, user))


def list_favorite_restaurants(
    session: Session, user: User, cursor: str | None, limit: int
) -> api.RestaurantPage:
    rows = session.exec(
        select(Restaurant)
        .join(FavoriteRestaurant, FavoriteRestaurant.restaurant_id == Restaurant.id)
        .where(FavoriteRestaurant.user_id == user.id)
        .order_by(col(FavoriteRestaurant.created_at).desc())
    ).all()
    page, next_cursor = paginate_list(list(rows), cursor, limit)
    return api.RestaurantPage(
        items=[_restaurant_schema(r, None, True) for r in page], next_cursor=next_cursor
    )


def add_favorite_restaurant(session: Session, user: User, restaurant_id: str) -> None:
    if session.get(Restaurant, restaurant_id) is None:
        raise not_found("Restaurant not found.")
    if session.get(FavoriteRestaurant, (user.id, restaurant_id)) is None:
        session.add(
            FavoriteRestaurant(user_id=user.id, restaurant_id=restaurant_id, created_at=utcnow())
        )
        session.commit()


def remove_favorite_restaurant(session: Session, user: User, restaurant_id: str) -> None:
    fav = session.get(FavoriteRestaurant, (user.id, restaurant_id))
    if fav is not None:
        session.delete(fav)
        session.commit()


def parse_types(raw: str | None, enum: type) -> list:
    values = split_csv(raw)
    if not values:
        raise validation_error(
            [field_error("types", api.Code.REQUIRED, "Select at least one type.")]
        )
    try:
        return list(dict.fromkeys(enum(v) for v in values))
    except ValueError:
        raise validation_error([field_error("types", api.Code.INVALID_VALUE, "Unknown type.")])


def search_local_food(
    session: Session,
    center: api.GeoPoint,
    radius: int,
    types: list[api.LocalFoodType],
    cursor: str | None,
    limit: int,
) -> api.LocalFoodPage:
    rows = _within(
        session,
        LocalFoodPlace,
        center,
        radius,
        col(LocalFoodPlace.type).in_([t.value for t in types]),
    )
    page, next_cursor = paginate_list(rows, cursor, limit)
    return api.LocalFoodPage(
        items=[api.LocalFoodPlace(**_place_fields(r, d), type=r.type) for r, d in page],
        next_cursor=next_cursor,
        search_center=center,
    )


def search_community(
    session: Session,
    center: api.GeoPoint,
    radius: int,
    types: list[api.CommunityOrgType],
    cursor: str | None,
    limit: int,
) -> api.CommunityOrgPage:
    rows = _within(
        session, CommunityOrg, center, radius, col(CommunityOrg.type).in_([t.value for t in types])
    )
    page, next_cursor = paginate_list(rows, cursor, limit)
    return api.CommunityOrgPage(
        items=[
            api.CommunityOrg(**_place_fields(r, d), type=r.type, how_to_help=r.how_to_help)
            for r, d in page
        ],
        next_cursor=next_cursor,
        search_center=center,
    )
