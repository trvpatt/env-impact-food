from uuid import UUID

from sqlmodel import Session, col, delete, select

from app.core.errors import field_error, not_found, validation_error
from app.core.pagination import paginate_query
from app.models import Food, ShoppingList, ShoppingListItem, User
from app.models.base import utcnow
from app.schemas import generated as api
from app.services.impact import UNIT_TO_KG


def _load_items(session: Session, list_ids: list[UUID]) -> dict[UUID, list[api.ShoppingListItem]]:
    rows = session.exec(
        select(ShoppingListItem, Food.name)
        .join(Food, Food.id == ShoppingListItem.food_id)
        .where(col(ShoppingListItem.shopping_list_id).in_(list_ids))
        .order_by(ShoppingListItem.position)
    ).all()
    items: dict[UUID, list[api.ShoppingListItem]] = {i: [] for i in list_ids}
    for item, food_name in rows:
        items[item.shopping_list_id].append(
            api.ShoppingListItem(
                id=item.id,
                food_id=item.food_id,
                food_name=food_name,
                quantity=item.quantity,
                unit=item.unit,
                price_cents=item.price_cents,
            )
        )
    return items


def _to_schema(sl: ShoppingList, items: list[api.ShoppingListItem]) -> api.ShoppingList:
    return api.ShoppingList(
        id=sl.id,
        name=sl.name,
        purchased_on=sl.purchased_on,
        items=items,
        created_at=sl.created_at,
        updated_at=sl.updated_at,
    )


def to_schema(session: Session, sl: ShoppingList) -> api.ShoppingList:
    return _to_schema(sl, _load_items(session, [sl.id])[sl.id])


def list_for_user(
    session: Session, user: User, cursor: str | None, limit: int
) -> api.ShoppingListPage:
    statement = (
        select(ShoppingList)
        .where(ShoppingList.user_id == user.id)
        .order_by(col(ShoppingList.created_at).desc(), col(ShoppingList.id).desc())
    )
    rows, next_cursor = paginate_query(session, statement, cursor, limit)
    items = _load_items(session, [r.id for r in rows])
    return api.ShoppingListPage(
        items=[_to_schema(r, items[r.id]) for r in rows], next_cursor=next_cursor
    )


def get_owned(session: Session, user: User, list_id: UUID) -> ShoppingList:
    sl = session.get(ShoppingList, list_id)
    if sl is None or sl.user_id != user.id:
        raise not_found("Shopping list not found.")
    return sl


def _validate_items(session: Session, items: list[api.ShoppingListItemInput]) -> None:
    food_ids = {i.food_id for i in items}
    known = (
        set(session.exec(select(Food.id).where(col(Food.id).in_(food_ids))).all())
        if food_ids
        else set()
    )
    errors = []
    for n, item in enumerate(items):
        if item.food_id not in known:
            errors.append(
                field_error(f"items.{n}.food_id", api.Code.INVALID_VALUE, "Unknown food.")
            )
        if item.unit.lower() not in UNIT_TO_KG and item.unit.lower() != "item":
            errors.append(
                field_error(
                    f"items.{n}.unit",
                    api.Code.INVALID_VALUE,
                    f"Unit must be one of: {', '.join([*UNIT_TO_KG, 'item'])}.",
                )
            )
    if errors:
        raise validation_error(errors)


def _write_items(
    session: Session, sl: ShoppingList, items: list[api.ShoppingListItemInput]
) -> None:
    for position, item in enumerate(items):
        session.add(
            ShoppingListItem(
                shopping_list_id=sl.id,
                position=position,
                food_id=item.food_id,
                quantity=item.quantity,
                unit=item.unit.lower(),
                price_cents=item.price_cents,
            )
        )


def create(session: Session, user: User, body: api.ShoppingListCreate) -> ShoppingList:
    _validate_items(session, body.items)
    sl = ShoppingList(user_id=user.id, name=body.name, purchased_on=body.purchased_on)
    session.add(sl)
    session.flush()
    _write_items(session, sl, body.items)
    session.commit()
    session.refresh(sl)
    return sl


def replace(
    session: Session, user: User, list_id: UUID, body: api.ShoppingListCreate
) -> ShoppingList:
    sl = get_owned(session, user, list_id)
    _validate_items(session, body.items)
    session.exec(delete(ShoppingListItem).where(ShoppingListItem.shopping_list_id == sl.id))
    sl.name = body.name
    sl.purchased_on = body.purchased_on
    sl.updated_at = utcnow()
    session.add(sl)
    _write_items(session, sl, body.items)
    session.commit()
    session.refresh(sl)
    return sl


def remove(session: Session, user: User, list_id: UUID) -> None:
    sl = get_owned(session, user, list_id)
    session.exec(delete(ShoppingListItem).where(ShoppingListItem.shopping_list_id == sl.id))
    session.delete(sl)
    session.commit()
