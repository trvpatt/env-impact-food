from datetime import date

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas import generated as api
from app.services import content, impact

router = APIRouter(prefix="/home", tags=["Home"])


@router.get("/weekly-impact", response_model=api.WeeklyImpact)
def get_weekly_impact(user: CurrentUser, session: SessionDep, week_start: date | None = None):
    return impact.weekly_impact(session, user, week_start)


@router.get("/big-picture", response_model=api.BigPicture)
def get_big_picture(user: CurrentUser, session: SessionDep):
    return content.big_picture(session, user)


@router.get("/daily-quote", response_model=api.Quote)
def get_daily_quote(_: CurrentUser, session: SessionDep):
    return content.daily_quote(session)
