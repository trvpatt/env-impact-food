from uuid import UUID

from sqlmodel import Session, col, select

from app.core.errors import not_found
from app.core.pagination import paginate_query
from app.models import Conversation, ConversationMessage, Survey, User
from app.models.base import utcnow
from app.schemas import generated as api
from app.services import rate_limit
from app.services.impact import load_lines

HISTORY_LIMIT = 50
TITLE_LENGTH = 60

SYSTEM_PROMPT = """\
You are Rooted's assistant. Rooted helps people eat more plant-forward food and see the \
environmental, health and money impact of their choices. Help the user with recipes, meal \
ideas, grocery choices, nutrition and the environmental impact of food. Keep answers practical \
and concise. You are not a doctor: for medical conditions, suggest the user check with a \
healthcare professional.

The user's current profile follows. Use it to tailor your answers.
"""


def to_conversation_schema(c: Conversation) -> api.Conversation:
    return api.Conversation.model_validate(c, from_attributes=True)


def to_message_schema(m: ConversationMessage) -> api.Message:
    return api.Message.model_validate(m, from_attributes=True)


def list_conversations(
    session: Session, user: User, cursor: str | None, limit: int
) -> api.ConversationPage:
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(col(Conversation.updated_at).desc(), Conversation.id)
    )
    rows, next_cursor = paginate_query(session, statement, cursor, limit)
    return api.ConversationPage(
        items=[to_conversation_schema(c) for c in rows], next_cursor=next_cursor
    )


def create_conversation(session: Session, user: User) -> Conversation:
    conversation = Conversation(user_id=user.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def get_owned(session: Session, user: User, conversation_id: UUID) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise not_found("Conversation not found.")
    return conversation


def list_messages(
    session: Session, user: User, conversation_id: UUID, cursor: str | None, limit: int
) -> api.MessagePage:
    get_owned(session, user, conversation_id)
    statement = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
    )
    rows, next_cursor = paginate_query(session, statement, cursor, limit)
    return api.MessagePage(items=[to_message_schema(m) for m in rows], next_cursor=next_cursor)


def _profile_snapshot(session: Session, user: User) -> str:
    survey = session.get(Survey, user.id)
    lines = [f"- Name: {user.first_name}"]
    if survey:
        if survey.diet:
            lines.append(f"- Diet: {survey.diet}")
        if survey.cuisine_ids:
            lines.append(f"- Favourite cuisines: {', '.join(survey.cuisine_ids)}")
        if survey.health_goals:
            lines.append(f"- Health goals: {', '.join(survey.health_goals)}")
        if survey.motivations:
            lines.append(f"- Motivations: {', '.join(survey.motivations)}")
    recent = sorted(load_lines(session, user_id=user.id), key=lambda line: line.day, reverse=True)
    foods = list(dict.fromkeys(line.food.name for line in recent))[:20]
    if foods:
        lines.append(f"- Recently bought: {', '.join(foods)}")
    return "\n".join(lines)


def start_turn(
    session: Session, user: User, conversation_id: UUID, content: str
) -> tuple[str, list[dict]]:
    """Save the user's message and return `(system_prompt, messages)` for the model."""
    conversation = get_owned(session, user, conversation_id)
    rate_limit.enforce(session, f"assistant:{user.id}", limit=30, window_seconds=3600)
    session.add(ConversationMessage(conversation_id=conversation.id, role="user", content=content))
    if conversation.title is None:
        conversation.title = content.strip()[:TITLE_LENGTH]
    conversation.updated_at = utcnow()
    session.add(conversation)
    session.commit()

    history = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(col(ConversationMessage.created_at).desc(), col(ConversationMessage.id).desc())
        .limit(HISTORY_LIMIT)
    ).all()
    messages = [{"role": m.role, "content": m.content} for m in reversed(history)]
    # The API requires the first message to be from the user.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return SYSTEM_PROMPT + _profile_snapshot(session, user), messages


def save_reply(session: Session, conversation_id: UUID, text: str) -> api.Message:
    message = ConversationMessage(conversation_id=conversation_id, role="assistant", content=text)
    conversation = session.get(Conversation, conversation_id)
    conversation.updated_at = utcnow()
    session.add(message)
    session.add(conversation)
    session.commit()
    session.refresh(message)
    return to_message_schema(message)
