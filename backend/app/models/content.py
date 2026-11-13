from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, utcnow


class Article(SQLModel, table=True):
    __tablename__ = "articles"

    id: str = Field(primary_key=True, max_length=64)
    title: str
    summary: str
    url: str
    image_url: str | None = None
    topic: str | None = Field(default=None, index=True)
    published_at: datetime = Field(sa_type=UTCDateTime, index=True)


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    title: str | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, index=True)


class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE")
    role: str  # user | assistant
    content: str
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, index=True)


class SupportTicket(SQLModel, table=True):
    __tablename__ = "support_tickets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    kind: str  # bug_report | contact
    subject: str | None = None
    body: str
    page_url: str | None = None
    user_agent: str | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
