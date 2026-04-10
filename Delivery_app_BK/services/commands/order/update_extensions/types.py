from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class OrderUpdateChangeFlags:
    address_changed: bool = False
    window_changed: bool = False


@dataclass(frozen=True)
class OrderUpdateDelta:
    order_instance: Any
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    flags: OrderUpdateChangeFlags
    changed_sections: tuple[str, ...] = ()
    delivery_plan: Any | None = None


@dataclass
class OrderUpdateExtensionContext:
    by_plan_type: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class OrderUpdateExtensionResult:
    instances: list[Any] = field(default_factory=list)
    post_flush_actions: list[Callable[[], None]] = field(default_factory=list)
    bundle_by_order_id: dict[int, dict[str, Any]] = field(default_factory=dict)
