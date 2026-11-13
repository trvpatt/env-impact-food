"""AI assistant model client (Anthropic)."""

import logging
from collections.abc import AsyncIterator
from typing import Protocol

import anthropic

from app.core.config import get_settings
from app.core.errors import ApiError

logger = logging.getLogger(__name__)

REFUSAL_TEXT = "Sorry, I can't help with that request."


class AssistantModel(Protocol):
    def stream_reply(self, system: str, messages: list[dict]) -> AsyncIterator[str]: ...


class AnthropicAssistantModel:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def stream_reply(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        """Yield reply text chunks. Raises `ApiError` for provider failures."""
        try:
            async with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                # Server-side fallback: on a safety decline, the API retries on a fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                produced = False
                async for text in stream.text_stream:
                    produced = True
                    yield text
                final = await stream.get_final_message()
            if final.stop_reason == "refusal" and not produced:
                yield REFUSAL_TEXT
        except anthropic.RateLimitError as exc:
            raise ApiError(
                429, "RATE_LIMITED", "The assistant is busy. Please try again shortly."
            ) from exc
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            logger.exception("Assistant model request failed")
            raise ApiError(
                502, "ASSISTANT_UNAVAILABLE", "The assistant is unavailable right now."
            ) from exc


def get_assistant_model() -> AssistantModel:
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "The assistant is not configured.")
    return AnthropicAssistantModel(
        settings.anthropic_api_key.get_secret_value(), settings.llm_model, settings.llm_max_tokens
    )
