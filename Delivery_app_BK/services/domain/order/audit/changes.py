from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

ENTITY_ORDER = "order"
ENTITY_NOTE = "note"
ENTITY_ITEM = "item"

FIELD_CREATED = "__created__"
FIELD_DELETED = "__deleted__"


@dataclass(frozen=True)
class OrderFieldChange:
    field_name: str
    from_value: Any
    to_value: Any
    entity_type: str = ENTITY_ORDER
    entity_id: str | None = None
    entity_label: str | None = None


def to_audit_value(value: Any) -> Any:
    """Return a detached, JSON-safe copy so later in-place mutation of the
    source object cannot rewrite a captured snapshot."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return to_audit_value(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): to_audit_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_audit_value(item) for item in value]
    return str(value)


def is_blank_audit_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def audit_values_differ(old: Any, new: Any) -> bool:
    if is_blank_audit_value(old) and is_blank_audit_value(new):
        return False
    return old != new
