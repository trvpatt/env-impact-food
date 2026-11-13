from sqlmodel import Session

from app.models import SupportTicket, User
from app.schemas import generated as api


def _save(session: Session, ticket: SupportTicket) -> api.SupportTicket:
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return api.SupportTicket(id=str(ticket.id), created_at=ticket.created_at)


def report_bug(session: Session, user: User, body: api.BugReportCreate) -> api.SupportTicket:
    return _save(
        session,
        SupportTicket(
            user_id=user.id,
            kind="bug_report",
            body=body.description,
            page_url=body.page_url,
            user_agent=body.user_agent,
        ),
    )


def contact_us(session: Session, user: User, body: api.ContactCreate) -> api.SupportTicket:
    return _save(
        session,
        SupportTicket(user_id=user.id, kind="contact", subject=body.subject, body=body.message),
    )
