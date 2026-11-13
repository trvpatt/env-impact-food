import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import get_engine
from app.core.deps import CurrentUser, SessionDep
from app.core.errors import ApiError
from app.core.pagination import CursorParam, LimitParam
from app.schemas import generated as api
from app.services import assistant as service
from app.services.llm import AssistantModel, get_assistant_model

router = APIRouter(prefix="/assistant/conversations", tags=["Assistant"])


@router.get("", response_model=api.ConversationPage)
def list_conversations(
    user: CurrentUser, session: SessionDep, cursor: CursorParam = None, limit: LimitParam = 20
):
    return service.list_conversations(session, user, cursor, limit)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=api.Conversation)
def create_conversation(user: CurrentUser, session: SessionDep):
    return service.to_conversation_schema(service.create_conversation(session, user))


@router.get("/{conversation_id}/messages", response_model=api.MessagePage)
def list_conversation_messages(
    conversation_id: UUID,
    user: CurrentUser,
    session: SessionDep,
    cursor: CursorParam = None,
    limit: LimitParam = 20,
):
    return service.list_messages(session, user, conversation_id, cursor, limit)


def _save_reply(conversation_id: UUID, text: str) -> api.Message:
    # Own session: a streaming body outlives the request-scoped one.
    with Session(get_engine()) as session:
        return service.save_reply(session, conversation_id, text)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/{conversation_id}/messages",
    response_model=api.Message,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def send_message(
    conversation_id: UUID,
    body: api.MessageCreate,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    model: Annotated[AssistantModel, Depends(get_assistant_model)],
):
    system, messages = await run_in_threadpool(
        service.start_turn, session, user, conversation_id, body.content
    )

    if "text/event-stream" not in request.headers.get("accept", ""):
        chunks = [chunk async for chunk in model.stream_reply(system, messages)]
        return await run_in_threadpool(_save_reply, conversation_id, "".join(chunks))

    async def events():
        chunks = []
        try:
            async for chunk in model.stream_reply(system, messages):
                chunks.append(chunk)
                yield _sse("delta", {"text": chunk})
        except ApiError as exc:
            yield _sse("error", {"code": exc.code, "message": exc.message})
            return
        message = await run_in_threadpool(_save_reply, conversation_id, "".join(chunks))
        yield _sse("done", message.model_dump(mode="json"))

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
