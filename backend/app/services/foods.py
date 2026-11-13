from sqlmodel import Session, func, select

from app.core.errors import not_found
from app.models import Food
from app.schemas import generated as api


def search(session: Session, q: str, limit: int) -> list[api.FoodSummary]:
    term = q.strip().lower()
    rows = session.exec(
        select(Food)
        .where(func.lower(Food.name).contains(term))
        # Names starting with the term rank first, then shorter (more generic) names.
        .order_by(func.lower(Food.name).startswith(term).desc(), func.length(Food.name), Food.name)
        .limit(limit)
    ).all()
    return [api.FoodSummary.model_validate(r, from_attributes=True) for r in rows]


def get(session: Session, food_id: str) -> api.FoodDetail:
    food = session.get(Food, food_id)
    if food is None:
        raise not_found("Food not found.")
    return api.FoodDetail.model_validate(food, from_attributes=True)
