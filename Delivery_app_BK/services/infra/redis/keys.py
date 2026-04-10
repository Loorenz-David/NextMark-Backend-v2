from __future__ import annotations

from flask import current_app


def get_redis_key_prefix() -> str:
    return current_app.config.get("REDIS_KEY_PREFIX", "nextmark")


def build_driver_location_key(team_id: int | str, driver_id: int | str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:driver:{team_id}:{driver_id}:location"


def build_driver_location_scan_pattern(team_id: int | str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:driver:{team_id}:*:location"


def build_notification_payload_key(notification_id: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:notification:{notification_id}"


def build_notification_unread_key(user_id: int | str, app_scope: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:notification:{app_scope}:{user_id}:unread"


def build_notification_count_key(user_id: int | str, app_scope: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:notification:{app_scope}:{user_id}:count"


# --- AI thread keys ---

def build_ai_thread_meta_key(thread_id: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:ai:thread:{thread_id}:meta"


def build_ai_thread_turns_key(thread_id: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:ai:thread:{thread_id}:turns"


def build_ai_turn_key(thread_id: str, turn_id: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:ai:thread:{thread_id}:turn:{turn_id}"


def build_ai_proposal_apply_key(proposal_hash: str) -> str:
    prefix = get_redis_key_prefix()
    return f"{prefix}:ai:proposal:applied:{proposal_hash}"
