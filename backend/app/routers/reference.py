from fastapi import APIRouter

from app.core.deps import SessionDep
from app.schemas import generated as api
from app.services import reference as service

router = APIRouter(tags=["Reference"])


@router.get("/reference/survey-options", response_model=api.SurveyOptions)
def get_survey_options(session: SessionDep):
    return service.survey_options(session)


@router.get("/reference/cuisines", response_model=list[api.Cuisine])
def list_cuisines(session: SessionDep):
    return service.list_cuisines(session)


@router.get("/reference/avatars", response_model=list[api.Avatar])
def list_avatars(session: SessionDep):
    return service.list_avatars(session)


@router.get("/health")
def health_check():
    return {"status": "ok"}
