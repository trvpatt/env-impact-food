from sqlmodel import Session, select

from app.core.errors import field_error, not_found, validation_error
from app.models import Cuisine, Survey, User
from app.models.base import utcnow
from app.schemas import generated as api

REQUIRED_FIELDS = ("diet", "cuisine_ids", "health_goals", "motivations")


def _dedupe(values: list) -> list:
    return list(dict.fromkeys(values))


def to_survey_schema(survey: Survey) -> api.SurveyResponse:
    return api.SurveyResponse(
        diet=survey.diet,
        cuisine_ids=survey.cuisine_ids,
        health_goals=survey.health_goals,
        motivations=survey.motivations,
        income_band=survey.income_band,
        completed_at=survey.completed_at,
        updated_at=survey.updated_at,
    )


def get_survey(session: Session, user: User) -> Survey:
    survey = session.get(Survey, user.id)
    if survey is None:
        raise not_found("Survey not started.")
    return survey


def save_progress(session: Session, user: User, body: api.SurveyUpdate) -> Survey:
    fields = body.model_fields_set
    if not fields:
        raise validation_error(
            [field_error("body", api.Code.REQUIRED, "Provide at least one answer.")]
        )
    if body.cuisine_ids:
        known = set(session.exec(select(Cuisine.id).where(Cuisine.id.in_(body.cuisine_ids))).all())
        unknown = [c for c in body.cuisine_ids if c not in known]
        if unknown:
            raise validation_error(
                [
                    field_error(
                        "cuisine_ids", api.Code.INVALID_VALUE, f"Unknown cuisine: {unknown[0]}"
                    )
                ]
            )

    survey = session.get(Survey, user.id) or Survey(user_id=user.id)
    if "diet" in fields:
        survey.diet = body.diet.value if body.diet else None
    if "cuisine_ids" in fields:
        survey.cuisine_ids = _dedupe(body.cuisine_ids) if body.cuisine_ids is not None else None
    if "health_goals" in fields:
        survey.health_goals = (
            _dedupe([g.value for g in body.health_goals]) if body.health_goals is not None else None
        )
    if "motivations" in fields:
        survey.motivations = (
            _dedupe([m.value for m in body.motivations]) if body.motivations is not None else None
        )
    if "income_band" in fields:
        survey.income_band = body.income_band.value if body.income_band else None
    survey.updated_at = utcnow()
    session.add(survey)
    session.commit()
    session.refresh(survey)
    return survey


def complete(session: Session, user: User) -> Survey:
    survey = session.get(Survey, user.id)
    missing = [f for f in REQUIRED_FIELDS if survey is None or not getattr(survey, f)]
    if missing:
        raise validation_error(
            [field_error(f, api.Code.REQUIRED, "Please answer this question.") for f in missing]
        )
    now = utcnow()
    survey.completed_at = survey.completed_at or now
    survey.updated_at = now
    user.onboarding_completed = True
    user.updated_at = now
    session.add(survey)
    session.add(user)
    session.commit()
    session.refresh(survey)
    return survey
