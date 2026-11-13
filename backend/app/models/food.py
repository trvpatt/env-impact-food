from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, utcnow


class Food(SQLModel, table=True):
    """Food item. Nutrition from USDA FoodData Central, footprint from Our World in Data."""

    __tablename__ = "foods"

    id: str = Field(primary_key=True, max_length=64)
    name: str = Field(index=True)
    category: str
    fdc_id: int | None = Field(default=None, index=True)
    # [{"name": "Protein", "amount": 21.0, "unit": "g"}, ...]
    nutrients_per_100g: list[dict] = Field(default_factory=list, sa_type=JSON)
    co2e_kg_per_kg: float | None = None
    water_liters_per_kg: float | None = None
    land_m2_per_kg: float | None = None
    avg_price_cents_per_kg: int | None = None


class ShoppingList(SQLModel, table=True):
    __tablename__ = "shopping_lists"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    name: str = Field(max_length=120)
    purchased_on: date | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, index=True)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class ShoppingListItem(SQLModel, table=True):
    __tablename__ = "shopping_list_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    shopping_list_id: UUID = Field(foreign_key="shopping_lists.id", index=True, ondelete="CASCADE")
    position: int
    food_id: str = Field(foreign_key="foods.id")
    quantity: float
    unit: str = Field(max_length=10)
    price_cents: int | None = None
