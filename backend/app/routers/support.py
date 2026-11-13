from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas import generated as api
from app.services import support as service

router = APIRouter(prefix="/support", tags=["Support"])


@router.post("/bug-reports", status_code=status.HTTP_201_CREATED, response_model=api.SupportTicket)
def report_bug(body: api.BugReportCreate, user: CurrentUser, session: SessionDep):
    return service.report_bug(session, user, body)


@router.post("/contact", status_code=status.HTTP_201_CREATED, response_model=api.SupportTicket)
def contact_us(body: api.ContactCreate, user: CurrentUser, session: SessionDep):
    return service.contact_us(session, user, body)
