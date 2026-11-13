"""Environmental, health and savings impact computed from users' shopping lists."""

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlmodel import Session, and_, col, func, or_, select

from app.models import Food, ShoppingList, ShoppingListItem, Survey, User
from app.models.base import utcnow
from app.schemas import generated as api

UNIT_TO_KG = {"g": 0.001, "kg": 1.0, "oz": 0.0283495, "lb": 0.453592, "ml": 0.001, "l": 1.0}

# PLACEHOLDER baseline for an average omnivore diet, per kg of food purchased.
# Replace with values derived from OWID data in data_pipeline/ before relying on the numbers.
BASELINE_CO2E_KG_PER_KG = 3.0
BASELINE_WATER_LITERS_PER_KG = 600.0
BASELINE_LAND_M2_PER_KG = 6.0
BASELINE_PRICE_CENTS_PER_KG = 900

CURRENCY = "usd"

# Survey field -> (keyword in USDA nutrient name, unit we report in)
_NUTRIENTS = {
    "fiber_g": ("fiber", "g"),
    "protein_g": ("protein", "g"),
    "saturated_fat_g": ("saturated", "g"),
    "cholesterol_mg": ("cholesterol", "mg"),
    "sodium_mg": ("sodium", "mg"),
}
_MASS_UNITS = {"g": 1.0, "mg": 0.001, "µg": 1e-6, "ug": 1e-6}


@dataclass
class Line:
    user_id: UUID
    day: date
    food: Food
    kg: float | None
    price_cents: int | None


def load_lines(
    session: Session,
    start: date | None = None,
    end: date | None = None,
    user_id: UUID | None = None,
) -> list[Line]:
    """Every purchased item in [start, end]. A list's date is `purchased_on`, else its creation day."""
    statement = (
        select(ShoppingList, ShoppingListItem, Food)
        .join(ShoppingListItem, ShoppingListItem.shopping_list_id == ShoppingList.id)
        .join(Food, Food.id == ShoppingListItem.food_id)
    )
    if user_id is not None:
        statement = statement.where(ShoppingList.user_id == user_id)
    if start is not None and end is not None:
        start_dt = datetime.combine(start, time.min, UTC)
        end_dt = datetime.combine(end + timedelta(days=1), time.min, UTC)
        statement = statement.where(
            or_(
                and_(
                    col(ShoppingList.purchased_on) >= start, col(ShoppingList.purchased_on) <= end
                ),
                and_(
                    col(ShoppingList.purchased_on).is_(None),
                    col(ShoppingList.created_at) >= start_dt,
                    col(ShoppingList.created_at) < end_dt,
                ),
            )
        )
    lines = []
    for sl, item, food in session.exec(statement).all():
        factor = UNIT_TO_KG.get(item.unit)
        lines.append(
            Line(
                user_id=sl.user_id,
                day=sl.purchased_on or sl.created_at.date(),
                food=food,
                kg=item.quantity * factor if factor else None,
                price_cents=item.price_cents,
            )
        )
    return lines


def environmental(lines: list[Line]) -> api.EnvironmentalImpact:
    co2 = water = land = 0.0
    for line in lines:
        if line.kg is None:
            continue
        if line.food.co2e_kg_per_kg is not None:
            co2 += line.kg * (BASELINE_CO2E_KG_PER_KG - line.food.co2e_kg_per_kg)
        if line.food.water_liters_per_kg is not None:
            water += line.kg * (BASELINE_WATER_LITERS_PER_KG - line.food.water_liters_per_kg)
        if line.food.land_m2_per_kg is not None:
            land += line.kg * (BASELINE_LAND_M2_PER_KG - line.food.land_m2_per_kg)
    return api.EnvironmentalImpact(
        co2e_kg_saved=round(co2, 2),
        water_liters_saved=round(water, 1),
        land_m2_saved=round(land, 2),
        animals_spared=None,
    )


def money_saved(lines: list[Line]) -> api.MoneySaved:
    saved = 0.0
    for line in lines:
        if line.kg is None:
            continue
        if line.price_cents is not None:
            actual = line.price_cents
        elif line.food.avg_price_cents_per_kg is not None:
            actual = line.food.avg_price_cents_per_kg * line.kg
        else:
            continue
        saved += BASELINE_PRICE_CENTS_PER_KG * line.kg - actual
    return api.MoneySaved(amount_cents=round(saved), currency=CURRENCY)


def _nutrient_amount(food: Food, keyword: str, unit: str) -> float:
    for n in food.nutrients_per_100g:
        if keyword in str(n.get("name", "")).lower():
            src = _MASS_UNITS.get(str(n.get("unit", unit)).lower(), _MASS_UNITS[unit])
            return float(n.get("amount", 0)) * src / _MASS_UNITS[unit]
    return 0.0


def health(lines: list[Line], goals: list[str]) -> api.HealthImpact:
    totals: dict[str, float] = defaultdict(float)
    sources: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for line in lines:
        if line.kg is None:
            continue
        for field, (keyword, unit) in _NUTRIENTS.items():
            amount = (
                _nutrient_amount(line.food, keyword, unit) * line.kg * 10
            )  # per 100 g -> per kg
            totals[field] += amount
            sources[field][line.food.name] += amount

    highlights = []
    for field, nutrient in (("fiber_g", "fiber"), ("protein_g", "protein")):
        if totals[field] <= 0:
            continue
        top = sorted(sources[field].items(), key=lambda kv: kv[1], reverse=True)[:2]
        names = " and ".join(name for name, _ in top)
        highlights.append(
            api.NutrientHighlight(
                nutrient=nutrient,
                message=f"{names} gave you {totals[field]:.0f} g of {nutrient}.",
                source_foods=[name for name, _ in top],
                amount=round(totals[field], 1),
                unit="g",
            )
        )

    summaries = {
        "lower_cholesterol": f"{totals['cholesterol_mg']:.0f} mg cholesterol and "
        f"{totals['saturated_fat_g']:.0f} g saturated fat from your groceries.",
        "build_muscle": f"{totals['protein_g']:.0f} g of protein from your groceries.",
        "athletic_performance": f"{totals['protein_g']:.0f} g of protein to fuel your training.",
        "lower_blood_pressure": f"{totals['sodium_mg']:.0f} mg sodium from your groceries.",
        "lose_weight": f"{totals['fiber_g']:.0f} g of fiber to help keep you full.",
    }
    return api.HealthImpact(
        **{field: round(totals[field], 1) for field in _NUTRIENTS},
        highlights=highlights,
        goal_progress=[
            api.GoalProgressItem(goal=g, summary=summaries[g]) for g in goals if g in summaries
        ],
    )


def _goals(session: Session, user: User) -> list[str]:
    survey = session.get(Survey, user.id)
    return (survey.health_goals or []) if survey else []


def weekly_impact(session: Session, user: User, week_start: date | None) -> api.WeeklyImpact:
    anchor = week_start or date.today()
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    lines = load_lines(session, start, end, user.id)
    env = environmental(lines)
    headline = (
        f"You helped avoid {env.co2e_kg_saved:.1f} kg of CO2 emissions this week!"
        if env.co2e_kg_saved > 0
        else "Add a shopping list to see your impact this week."
    )
    return api.WeeklyImpact(
        week_start=start,
        week_end=end,
        environmental=env,
        health=health(lines, _goals(session, user)),
        money_saved=money_saved(lines),
        headline=headline,
    )


def period_range(period: api.ReportPeriod, anchor: date) -> tuple[date, date]:
    if period == api.ReportPeriod.week:
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period == api.ReportPeriod.month:
        return anchor.replace(day=1), anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
    return date(anchor.year, 1, 1), date(anchor.year, 12, 31)


def report(
    session: Session, user: User, period: api.ReportPeriod, anchor: date | None
) -> api.Report:
    start, end = period_range(period, anchor or date.today())
    lines = load_lines(session, start, end, user.id)

    if period == api.ReportPeriod.year:
        bucket_of = lambda d: d.replace(day=1)  # noqa: E731
        buckets = [date(start.year, m, 1) for m in range(1, 13)]
    else:
        bucket_of = lambda d: d  # noqa: E731
        buckets = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    by_bucket: dict[date, list[Line]] = defaultdict(list)
    for line in lines:
        by_bucket[bucket_of(line.day)].append(line)

    return api.Report(
        period=period,
        start_date=start,
        end_date=end,
        environmental=environmental(lines),
        health=health(lines, _goals(session, user)),
        money_saved=money_saved(lines),
        series=[
            api.ReportDataPoint(
                bucket_start=b,
                environmental=environmental(by_bucket[b]),
                money_saved=money_saved(by_bucket[b]),
            )
            for b in buckets
        ],
    )


def community_stats(
    session: Session, user: User
) -> tuple[api.EnvironmentalImpact, api.EnvironmentalImpact, float, int]:
    """Returns (all-time total, this week, user's share of this week in %, active members)."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_lines = load_lines(session, week_start, week_start + timedelta(days=6))
    this_week = environmental(week_lines)
    mine = environmental([line for line in week_lines if line.user_id == user.id])
    share = (
        round(100 * mine.co2e_kg_saved / this_week.co2e_kg_saved, 1)
        if this_week.co2e_kg_saved > 0
        else 0.0
    )
    active_members = session.exec(
        select(func.count(func.distinct(ShoppingList.user_id))).where(
            col(ShoppingList.created_at) >= utcnow() - timedelta(days=30)
        )
    ).one()
    return environmental(load_lines(session)), this_week, max(share, 0.0), active_members
