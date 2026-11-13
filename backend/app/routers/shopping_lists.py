from uuid import UUID

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.core.pagination import CursorParam, LimitParam
from app.schemas import generated as api
from app.services import shopping_lists as service

router = APIRouter(prefix="/shopping-lists", tags=["Shopping Lists"])


@router.get("", response_model=api.ShoppingListPage)
def list_shopping_lists(
    user: CurrentUser, session: SessionDep, cursor: CursorParam = None, limit: LimitParam = 20
):
    return service.list_for_user(session, user, cursor, limit)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=api.ShoppingList)
def create_shopping_list(body: api.ShoppingListCreate, user: CurrentUser, session: SessionDep):
    return service.to_schema(session, service.create(session, user, body))


@router.get("/{shopping_list_id}", response_model=api.ShoppingList)
def get_shopping_list(shopping_list_id: UUID, user: CurrentUser, session: SessionDep):
    return service.to_schema(session, service.get_owned(session, user, shopping_list_id))


@router.put("/{shopping_list_id}", response_model=api.ShoppingList)
def replace_shopping_list(
    shopping_list_id: UUID, body: api.ShoppingListCreate, user: CurrentUser, session: SessionDep
):
    return service.to_schema(session, service.replace(session, user, shopping_list_id, body))


@router.delete("/{shopping_list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shopping_list(shopping_list_id: UUID, user: CurrentUser, session: SessionDep):
    service.remove(session, user, shopping_list_id)
