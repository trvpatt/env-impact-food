from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import CursorParam, LimitParam
from app.schemas import generated as api
from app.services import recipes as service

router = APIRouter(tags=["Recipes"])


@router.get("/recipes", response_model=api.RecipeSummaryPage)
def search_recipes(
    user: CurrentUser,
    session: SessionDep,
    diet: api.Diet | None = None,
    cuisine_ids: Annotated[str | None, Query(description="Comma-separated cuisine ids.")] = None,
    favorites_only: bool = False,
    ingredients: Annotated[
        str | None, Query(description="Comma-separated, e.g. `chickpeas,spinach`.")
    ] = None,
    cursor: CursorParam = None,
    limit: LimitParam = 20,
):
    return service.search(
        session, user, diet, cuisine_ids, favorites_only, ingredients, cursor, limit
    )


@router.get("/recipes/{recipe_id}", response_model=api.Recipe)
def get_recipe(recipe_id: UUID, user: CurrentUser, session: SessionDep):
    return service.get(session, user, recipe_id)


@router.get("/users/me/favorites/recipes", response_model=api.RecipeSummaryPage)
def list_favorite_recipes(
    user: CurrentUser, session: SessionDep, cursor: CursorParam = None, limit: LimitParam = 20
):
    return service.list_favorites(session, user, cursor, limit)


@router.put("/users/me/favorites/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite_recipe(recipe_id: UUID, user: CurrentUser, session: SessionDep):
    service.add_favorite(session, user, recipe_id)


@router.delete("/users/me/favorites/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite_recipe(recipe_id: UUID, user: CurrentUser, session: SessionDep):
    service.remove_favorite(session, user, recipe_id)
