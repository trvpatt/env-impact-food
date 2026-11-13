from datetime import date

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas import generated as api
from app.services import impact

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/me", response_model=api.Report)
def get_my_report(
    period: api.ReportPeriod,
    user: CurrentUser,
    session: SessionDep,
    anchor_date: date | None = None,
):
    return impact.report(session, user, period, anchor_date)
