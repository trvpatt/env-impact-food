from sqlmodel import Session, select

from app.models import Avatar, Cuisine
from app.schemas import generated as api

DIET_LABELS = {
    api.Diet.vegan: ("Vegan", "No animal products."),
    api.Diet.vegetarian: ("Vegetarian", "No meat or fish."),
    api.Diet.mediterranean: ("Mediterranean", "Mostly plants, with some fish and dairy."),
}
HEALTH_GOAL_LABELS = {
    api.HealthGoal.lower_cholesterol: "Lower cholesterol",
    api.HealthGoal.build_muscle: "Build muscle",
    api.HealthGoal.lower_blood_pressure: "Lower blood pressure",
    api.HealthGoal.lose_weight: "Lose weight",
    api.HealthGoal.athletic_performance: "Athletic performance",
}
MOTIVATION_LABELS = {
    api.Motivation.environment: "The environment",
    api.Motivation.personal_health: "Personal health",
    api.Motivation.factory_farming: "Ending factory farming",
}
INCOME_BAND_LABELS = {
    api.IncomeBand.under_25k: "Under $25k",
    api.IncomeBand.field_25k_50k: "$25k–$50k",
    api.IncomeBand.field_50k_75k: "$50k–$75k",
    api.IncomeBand.field_75k_100k: "$75k–$100k",
    api.IncomeBand.field_100k_150k: "$100k–$150k",
    api.IncomeBand.field_150k_200k: "$150k–$200k",
    api.IncomeBand.field_200k_plus: "$200k+",
    api.IncomeBand.prefer_not_to_say: "Prefer not to say",
}
INCOME_BAND_NOTE = (
    "We use this data to give you more catered restaurant recommendations and food item lists."
)


def _options(labels: dict) -> list[api.LabeledOption]:
    return [api.LabeledOption(value=k.value, label=v) for k, v in labels.items()]


def list_cuisines(session: Session) -> list[api.Cuisine]:
    rows = session.exec(select(Cuisine).order_by(Cuisine.sort_order, Cuisine.name)).all()
    return [api.Cuisine.model_validate(r, from_attributes=True) for r in rows]


def list_avatars(session: Session) -> list[api.Avatar]:
    rows = session.exec(select(Avatar).order_by(Avatar.sort_order, Avatar.name)).all()
    return [api.Avatar.model_validate(r, from_attributes=True) for r in rows]


def survey_options(session: Session) -> api.SurveyOptions:
    return api.SurveyOptions(
        diets=[
            api.LabeledOption(value=k.value, label=label, description=desc)
            for k, (label, desc) in DIET_LABELS.items()
        ],
        cuisines=list_cuisines(session),
        health_goals=_options(HEALTH_GOAL_LABELS),
        motivations=_options(MOTIVATION_LABELS),
        income_bands=_options(INCOME_BAND_LABELS),
        income_band_note=INCOME_BAND_NOTE,
    )
