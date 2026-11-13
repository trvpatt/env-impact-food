from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, utcnow


class PlaceBase(SQLModel):
    """Columns shared by every map/list result."""

    id: str = Field(primary_key=True, max_length=64)
    name: str
    address: dict = Field(sa_type=JSON)
    lat: float = Field(index=True)
    lng: float = Field(index=True)
    # [{"day_of_week": 0, "opens": "09:00", "closes": "17:00", "note": null}, ...]
    hours: list[dict] = Field(default_factory=list, sa_type=JSON)
    # {"phone": ..., "website": ..., "email": ...}
    contact: dict = Field(default_factory=dict, sa_type=JSON)
    image_url: str | None = None


class Restaurant(PlaceBase, table=True):
    __tablename__ = "restaurants"

    cuisine_ids: list[str] = Field(default_factory=list, sa_type=JSON)
    diets_supported: list[str] = Field(default_factory=list, sa_type=JSON)
    price_level: int | None = None
    rating: float | None = None


class LocalFoodPlace(PlaceBase, table=True):
    __tablename__ = "local_food_places"

    type: str = Field(index=True)  # farmers_market | coop | local_grocer


class CommunityOrg(PlaceBase, table=True):
    __tablename__ = "community_orgs"

    type: str = Field(index=True)  # food_pantry | soup_kitchen | community_garden
    how_to_help: str | None = None


class FavoriteRestaurant(SQLModel, table=True):
    __tablename__ = "favorite_restaurants"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    restaurant_id: str = Field(foreign_key="restaurants.id", primary_key=True, ondelete="CASCADE")
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
