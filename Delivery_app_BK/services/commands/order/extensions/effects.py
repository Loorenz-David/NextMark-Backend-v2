from __future__ import annotations

from collections.abc import Callable
from typing import Any


def merge_bundle_map(
    target: dict[Any, dict[str, Any]],
    incoming: dict[Any, dict[str, Any]],
) -> None:
    for key, payload in (incoming or {}).items():
        existing = target.get(key, {})
        existing.update(payload or {})
        target[key] = existing


def wrap_post_flush_action(
    action: Callable[[], None],
    *,
    after: Callable[[], None] | None = None,
) -> Callable[[], None]:
    def _wrapped() -> None:
        action()
        if after:
            after()

    return _wrapped
