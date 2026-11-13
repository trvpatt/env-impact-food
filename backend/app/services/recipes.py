import re
from collections import defaultdict
from uuid import UUID

from sqlmodel import Session, col, func, select

from app.core.errors import ApiError, field_error, not_found, validation_error
from app.core.pagination import paginate_list, split_csv
from app.models import FavoriteRecipe, Recipe, RecipeIngredient, User
from app.models.base import utcnow
from app.schemas import generated as api

MAX_INGREDIENTS = 30
_INGREDIENT_RE = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,59}$")


def parse_ingredients(raw: str | None) -> list[str]:
    if raw is None:
        return []
    terms = [t.strip().lower() for t in raw.split(",")]
    if len(terms) > MAX_INGREDIENTS or not all(_INGREDIENT_RE.match(t) for t in terms):
        raise validation_error(
            [
                field_error(
                    "ingredients",
                    api.Code.INVALID_INGREDIENT_FORMAT,
                    "Please follow the formatting instructions!",
                )
            ]
        )
    return list(dict.fromkeys(terms))


def _total_time(r: Recipe) -> int | None:
    if r.prep_time_minutes is None and r.cook_time_minutes is None:
        return None
    return (r.prep_time_minutes or 0) + (r.cook_time_minutes or 0)


def _summary_fields(r: Recipe, favorite: bool, matched: int | None = None) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "image_url": r.image_url,
        "cuisine_id": r.cuisine_id,
        "diets": r.diets,
        "total_time_minutes": _total_time(r),
        "is_favorite": favorite,
        "matched_ingredient_count": matched,
    }


def _favorite_ids(session: Session, user: User) -> set[UUID]:
    return set(
        session.exec(
            select(FavoriteRecipe.recipe_id).where(FavoriteRecipe.user_id == user.id)
        ).all()
    )


def search(
    session: Session,
    user: User,
    diet: api.Diet | None,
    cuisine_ids: str | None,
    favorites_only: bool,
    ingredients: str | None,
    cursor: str | None,
    limit: int,
) -> api.RecipeSummaryPage:
    terms = parse_ingredients(ingredients)
    favorites = _favorite_ids(session, user)
    statement = select(Recipe).order_by(col(Recipe.created_at).desc(), Recipe.title)
    if favorites_only:
        if not favorites:
            raise ApiError(
                409,
                "NO_FAVORITE_RECIPES",
                "please favorite some recipes first prior to selecting this filter!",
            )
        statement = statement.where(col(Recipe.id).in_(favorites))
    cuisines = split_csv(cuisine_ids)
    if cuisines:
        statement = statement.where(col(Recipe.cuisine_id).in_(cuisines))
    recipes = [r for r in session.exec(statement).all() if diet is None or diet.value in r.diets]

    matches: dict[UUID, int] = {}
    if terms:
        ingredient_rows = session.exec(
            select(RecipeIngredient.recipe_id, RecipeIngredient.name).where(
                col(RecipeIngredient.recipe_id).in_([r.id for r in recipes])
            )
        ).all()
        names: dict[UUID, list[str]] = defaultdict(list)
        for recipe_id, name in ingredient_rows:
            names[recipe_id].append(name.lower())
        for r in recipes:
            matches[r.id] = sum(any(t in n for n in names[r.id]) for t in terms)
        recipes = sorted((r for r in recipes if matches[r.id] > 0), key=lambda r: -matches[r.id])

    page, next_cursor = paginate_list(recipes, cursor, limit)
    return api.RecipeSummaryPage(
        items=[
            api.RecipeSummary(
                **_summary_fields(r, r.id in favorites, matches.get(r.id) if terms else None)
            )
            for r in page
        ],
        next_cursor=next_cursor,
    )


def get(session: Session, user: User, recipe_id: UUID) -> api.Recipe:
    r = session.get(Recipe, recipe_id)
    if r is None:
        raise not_found("Recipe not found.")
    ingredients = session.exec(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id == r.id)
        .order_by(RecipeIngredient.position)
    ).all()
    return api.Recipe(
        **_summary_fields(r, r.id in _favorite_ids(session, user)),
        description=r.description,
        servings=r.servings,
        prep_time_minutes=r.prep_time_minutes,
        cook_time_minutes=r.cook_time_minutes,
        ingredients=[
            api.RecipeIngredient.model_validate(i, from_attributes=True) for i in ingredients
        ],
        steps=r.steps,
        nutrition_per_serving=r.nutrition_per_serving,
        environmental_per_serving=r.environmental_per_serving,
    )


def list_favorites(
    session: Session, user: User, cursor: str | None, limit: int
) -> api.RecipeSummaryPage:
    rows = session.exec(
        select(Recipe)
        .join(FavoriteRecipe, FavoriteRecipe.recipe_id == Recipe.id)
        .where(FavoriteRecipe.user_id == user.id)
        .order_by(col(FavoriteRecipe.created_at).desc())
    ).all()
    page, next_cursor = paginate_list(list(rows), cursor, limit)
    return api.RecipeSummaryPage(
        items=[api.RecipeSummary(**_summary_fields(r, True)) for r in page], next_cursor=next_cursor
    )


def add_favorite(session: Session, user: User, recipe_id: UUID) -> None:
    if session.get(Recipe, recipe_id) is None:
        raise not_found("Recipe not found.")
    if session.get(FavoriteRecipe, (user.id, recipe_id)) is None:
        session.add(FavoriteRecipe(user_id=user.id, recipe_id=recipe_id, created_at=utcnow()))
        session.commit()


def remove_favorite(session: Session, user: User, recipe_id: UUID) -> None:
    fav = session.get(FavoriteRecipe, (user.id, recipe_id))
    if fav is not None:
        session.delete(fav)
        session.commit()


def most_favorited(session: Session, user: User, limit: int) -> list[api.RecipeSummary]:
    count = func.count(col(FavoriteRecipe.user_id))
    rows = session.exec(
        select(Recipe)
        .join(FavoriteRecipe, FavoriteRecipe.recipe_id == Recipe.id)
        .group_by(Recipe.id)
        .order_by(count.desc(), Recipe.title)
        .limit(limit)
    ).all()
    favorites = _favorite_ids(session, user)
    return [api.RecipeSummary(**_summary_fields(r, r.id in favorites)) for r in rows]
