from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AITokenTelemetry:
    request_id: str | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


_ai_token_telemetry_ctx: ContextVar[AITokenTelemetry | None] = ContextVar(
    "ai_token_telemetry",
    default=None,
)


def start_ai_request_telemetry(request_id: str | None) -> None:
    _ai_token_telemetry_ctx.set(AITokenTelemetry(request_id=request_id))


def clear_ai_request_telemetry() -> None:
    _ai_token_telemetry_ctx.set(None)


def record_ai_token_usage(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    state = _ai_token_telemetry_ctx.get()
    if state is None:
        return

    state.prompt_tokens += int(prompt_tokens or 0)
    state.completion_tokens += int(completion_tokens or 0)
    state.total_tokens += int(total_tokens or 0)
    state.calls += 1


def log_ai_request_telemetry(*, capability_name: str, stage_name: str) -> None:
    state = _ai_token_telemetry_ctx.get()
    if state is None:
        return

    logger.info(
        "AI token usage aggregate | request_id=%s | capability=%s | stage=%s | llm_calls=%d | prompt_tokens=%d | completion_tokens=%d | total_tokens=%d",
        state.request_id,
        capability_name,
        stage_name,
        state.calls,
        state.prompt_tokens,
        state.completion_tokens,
        state.total_tokens,
    )
