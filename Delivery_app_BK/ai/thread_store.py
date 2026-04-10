from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from Delivery_app_BK.services.infra.redis.client import get_current_redis_connection
from Delivery_app_BK.services.infra.redis.json import dumps_json, loads_json
from Delivery_app_BK.services.infra.redis.keys import (
    build_ai_thread_meta_key,
    build_ai_thread_turns_key,
    build_ai_turn_key,
)

from .errors import ThreadAccessError, ThreadNotFoundError
from .schemas import AIThreadMetadata, AIThreadTurn

logger = logging.getLogger(__name__)

THREAD_TTL = 86_400       # 24 hours in seconds
MAX_STORED_TURNS = 100    # prune oldest when exceeded
MAX_REPLAY_TURNS = 20     # turns sent to planner per request


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_thread(
    *,
    user_id: int,
    app_scope: str,
    session_scope_id: str | None = None,
    current_workspace: str | None = None,
) -> AIThreadMetadata:
    redis = get_current_redis_connection()
    thread_id = _new_id("thr")
    now = _now_iso()

    meta = AIThreadMetadata(
        thread_id=thread_id,
        user_id=user_id,
        app_scope=app_scope,
        session_scope_id=session_scope_id,
        current_workspace=current_workspace,
        created_at=now,
        updated_at=now,
    )

    meta_key = build_ai_thread_meta_key(thread_id)
    redis.set(meta_key, dumps_json(meta.model_dump()), ex=THREAD_TTL)

    logger.info("AI thread created | thread_id=%s | user_id=%s", thread_id, user_id)
    return meta


def get_thread_metadata(thread_id: str) -> AIThreadMetadata | None:
    redis = get_current_redis_connection()
    meta_key = build_ai_thread_meta_key(thread_id)
    raw = redis.get(meta_key)
    if not raw:
        return None
    data = loads_json(raw)
    return AIThreadMetadata(**data)


def assert_thread_access(
    thread_id: str,
    *,
    user_id: int,
    app_scope: str,
    session_scope_id: str | None,
) -> AIThreadMetadata:
    meta = get_thread_metadata(thread_id)
    if meta is None:
        raise ThreadNotFoundError(thread_id)
    if meta.user_id != user_id or meta.app_scope != app_scope:
        raise ThreadAccessError(thread_id)
    return meta


def append_turn(thread_id: str, turn: AIThreadTurn) -> None:
    redis = get_current_redis_connection()
    turns_key = build_ai_thread_turns_key(thread_id)
    turn_key = build_ai_turn_key(thread_id, turn.id)

    with redis.pipeline() as pipe:
        pipe.set(turn_key, dumps_json(turn.model_dump()), ex=THREAD_TTL)
        pipe.rpush(turns_key, turn.id)
        pipe.expire(turns_key, THREAD_TTL)
        pipe.execute()

    _refresh_thread_ttl(redis, thread_id)
    _prune_turns_if_needed(redis, thread_id)


def list_turns(thread_id: str, limit: int = MAX_REPLAY_TURNS) -> list[AIThreadTurn]:
    redis = get_current_redis_connection()
    turns_key = build_ai_thread_turns_key(thread_id)

    # lrange -limit -1 gets the most recent N turns
    turn_ids = redis.lrange(turns_key, -limit, -1)
    turns: list[AIThreadTurn] = []
    for turn_id in turn_ids:
        turn_key = build_ai_turn_key(thread_id, turn_id)
        raw = redis.get(turn_key)
        if raw:
            turns.append(AIThreadTurn(**loads_json(raw)))

    _refresh_thread_ttl(redis, thread_id)
    return turns


def list_all_turns(thread_id: str) -> list[AIThreadTurn]:
    """Return all stored turns (for GET /threads/<id> rehydration)."""
    redis = get_current_redis_connection()
    turns_key = build_ai_thread_turns_key(thread_id)
    turn_ids = redis.lrange(turns_key, 0, -1)
    turns: list[AIThreadTurn] = []
    for turn_id in turn_ids:
        turn_key = build_ai_turn_key(thread_id, turn_id)
        raw = redis.get(turn_key)
        if raw:
            turns.append(AIThreadTurn(**loads_json(raw)))
    return turns


def build_user_turn(
    thread_id: str,
    content: str,
    *,
    interaction_response_id: str | None = None,
    interaction_form: dict | None = None,
) -> AIThreadTurn:
    return AIThreadTurn(
        id=_new_id("turn"),
        thread_id=thread_id,
        role="user",
        content=content,
        created_at=_now_iso(),
        interaction_response_id=interaction_response_id,
        interaction_form=interaction_form,
    )


def build_tool_turn(thread_id: str, tool_name: str, params: dict, result: dict) -> AIThreadTurn:
    return AIThreadTurn(
        id=_new_id("turn"),
        thread_id=thread_id,
        role="tool",
        content=f"Tool {tool_name} executed",
        created_at=_now_iso(),
        tool_name=tool_name,
        tool_params=params,
        tool_result=result,
    )


def build_assistant_turn(
    thread_id: str,
    content: str,
    *,
    tool_trace=None,
    blocks=None,
    actions=None,
    interactions=None,
    data=None,
    status_label: str | None = None,
    awaiting_response: bool | None = None,
    interaction_kind: str | None = None,
    interaction_id: str | None = None,
) -> AIThreadTurn:
    return AIThreadTurn(
        id=_new_id("turn"),
        thread_id=thread_id,
        role="assistant",
        content=content,
        created_at=_now_iso(),
        tool_trace=tool_trace,
        blocks=blocks,
        actions=actions,
        interactions=interactions,
        data=data,
        status_label=status_label,
        awaiting_response=awaiting_response,
        interaction_kind=interaction_kind,
        interaction_id=interaction_id,
    )


# ---------------------------------------------------------------------------
# Phase 2+: Pause/Resume interaction state (scaffolded in Phase 1)
# ---------------------------------------------------------------------------

def mark_turn_awaiting_response(
    thread_id: str,
    turn_id: str,
    interaction_kind: str,
    interaction_id: str,
) -> None:
    """Mark a turn as awaiting user response to a blocking interaction (question, confirm).
    
    Args:
        thread_id: Thread ID
        turn_id: Assistant turn ID awaiting response
        interaction_kind: "question" or "confirm"
        interaction_id: ID of the interaction being awaited
    
    Scaffolded for Phase 2. Currently not called by backend.
    """
    redis = get_current_redis_connection()
    turn_key = build_ai_turn_key(thread_id, turn_id)
    
    # Fetch, update, and re-save the turn
    raw = redis.get(turn_key)
    if not raw:
        logger.warning("Turn not found for marking awaiting: %s", turn_id)
        return
    
    turn_data = loads_json(raw)
    turn_data["awaiting_response"] = True
    turn_data["interaction_kind"] = interaction_kind
    turn_data["interaction_id"] = interaction_id
    
    redis.set(turn_key, dumps_json(turn_data), ex=THREAD_TTL)
    logger.debug(
        "Marked turn as awaiting response | thread=%s | turn=%s | kind=%s",
        thread_id, turn_id, interaction_kind
    )


def get_turn_awaiting_response(thread_id: str) -> AIThreadTurn | None:
    """Fetch the most recent assistant turn awaiting user response.
    
    Returns the turn if found and awaiting_response=true, else None.
    
    Scaffolded for Phase 2. Currently not called by backend.
    """
    redis = get_current_redis_connection()
    turns_key = build_ai_thread_turns_key(thread_id)
    
    # Walk backward through turns to find the first awaiting response
    turn_ids = redis.lrange(turns_key, 0, -1)
    for turn_id in reversed(turn_ids):
        turn_key = build_ai_turn_key(thread_id, turn_id)
        raw = redis.get(turn_key)
        if not raw:
            continue
        
        turn = AIThreadTurn(**loads_json(raw))
        if turn.awaiting_response:
            return turn
    
    return None


def clear_turn_awaiting_response(thread_id: str, turn_id: str) -> None:
    """Clear awaiting-response marker on a turn after a valid interaction response."""
    redis = get_current_redis_connection()
    turn_key = build_ai_turn_key(thread_id, turn_id)

    raw = redis.get(turn_key)
    if not raw:
        logger.warning("Turn not found for clearing awaiting flag: %s", turn_id)
        return

    turn_data = loads_json(raw)
    turn_data["awaiting_response"] = False
    turn_data["interaction_kind"] = None
    turn_data["interaction_id"] = None

    redis.set(turn_key, dumps_json(turn_data), ex=THREAD_TTL)
    logger.debug("Cleared awaiting response | thread=%s | turn=%s", thread_id, turn_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _refresh_thread_ttl(redis, thread_id: str) -> None:
    meta_key = build_ai_thread_meta_key(thread_id)
    turns_key = build_ai_thread_turns_key(thread_id)
    redis.expire(meta_key, THREAD_TTL)
    redis.expire(turns_key, THREAD_TTL)


def _prune_turns_if_needed(redis, thread_id: str) -> None:
    turns_key = build_ai_thread_turns_key(thread_id)
    total = redis.llen(turns_key)
    if total <= MAX_STORED_TURNS:
        return

    excess = total - MAX_STORED_TURNS
    stale_ids = redis.lrange(turns_key, 0, excess - 1)
    with redis.pipeline() as pipe:
        for turn_id in stale_ids:
            pipe.delete(build_ai_turn_key(thread_id, turn_id))
        pipe.ltrim(turns_key, excess, -1)
        pipe.execute()

    logger.debug("Pruned %d old turns from thread %s", excess, thread_id)
