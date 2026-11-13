from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, utcnow


class Recipe(SQLModel, table=True):
    __tablename__ = "recipes"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    image_url: str
    cuisine_id: str = Field(foreign_key="cuisines.id", index=True)
    diets: list[str] = Field(default_factory=list, sa_type=JSON)
    description: str | None = None
    servings: int = 1
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    steps: list[str] = Field(default_factory=list, sa_type=JSON)
    nutrition_per_serving: dict | None = Field(default=None, sa_type=JSON)
    environmental_per_serving: dict | None = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class RecipeIngredient(SQLModel, table=True):
    __tablename__ = "recipe_ingredients"

    id: int | None = Field(default=None, primary_key=True)
    recipe_id: UUID = Field(foreign_key="recipes.id", index=True, ondelete="CASCADE")
    position: int
    food_id: str | None = Field(default=None, foreign_key="foods.id")
    name: str = Field(index=True)
    quantity: float | None = None
    unit: str | None = None
    display_text: str


class FavoriteRecipe(SQLModel, table=True):
    __tablename__ = "favorite_recipes"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    recipe_id: UUID = Field(foreign_key="recipes.id", primary_key=True, ondelete="CASCADE")
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
