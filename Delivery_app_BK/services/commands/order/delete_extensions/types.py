from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class OrderDeleteDelta:
    order_id: int
    order_client_id: str
    delivery_plan: Any | None = None


@dataclass
class OrderDeleteExtensionContext:
    by_plan_type: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class OrderDeleteExtensionResult:
    instances: list[Any] = field(default_factory=list)
    post_flush_actions: list[Callable[[], None]] = field(default_factory=list)
    updated_bundles: list[dict[str, Any]] = field(default_factory=list)
