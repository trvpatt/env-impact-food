from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas import generated as api
from app.services import survey as service

router = APIRouter(prefix="/users/me/survey", tags=["Survey"])


@router.get("", response_model=api.SurveyResponse)
def get_my_survey(user: CurrentUser, session: SessionDep):
    return service.to_survey_schema(service.get_survey(session, user))


@router.patch("", response_model=api.SurveyResponse)
def save_survey_progress(body: api.SurveyUpdate, user: CurrentUser, session: SessionDep):
    return service.to_survey_schema(service.save_progress(session, user, body))


@router.post("/complete", response_model=api.SurveyResponse)
def complete_survey(user: CurrentUser, session: SessionDep):
    return service.to_survey_schema(service.complete(session, user))
