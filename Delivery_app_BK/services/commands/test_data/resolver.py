from __future__ import annotations

from .ref_map import REF_FIELD_MAP
from .registry import RefResolutionError, Registry


def resolve_item(entity_key: str, item: dict, registry: Registry) -> dict:
    """Strip $id, resolve all $key refs, and return a clean dict for the processor."""
    ref_rules = REF_FIELD_MAP.get(entity_key, {})
    output: dict = {}

    for key, value in item.items():
        if key == "$id":
            continue

        if key.startswith("_"):
            continue

        if key.startswith("$"):
            if key not in ref_rules:
                raise RefResolutionError(
                    f"Unknown $ref key {key!r} on entity {entity_key!r}. "
                    f"Registered $refs for this entity: {sorted(ref_rules)}"
                )
            rule = ref_rules[key]

            if isinstance(rule, tuple):
                fk_column, ref_type = rule
                if ref_type != "list":
                    raise ValueError(f"Unknown ref_type {ref_type!r} in REF_FIELD_MAP")
                if not isinstance(value, list):
                    raise RefResolutionError(
                        f"{key} on {entity_key!r} must be a list of $id strings."
                    )
                output[fk_column] = [
                    _resolve_single(entity_key, key, ref, registry) for ref in value
                ]
            else:
                output[rule] = _resolve_single(entity_key, key, value, registry)
        else:
            output[key] = value

    return output


def _resolve_single(entity_key: str, ref_key: str, sid: str, registry: Registry) -> int:
    if not isinstance(sid, str):
        raise RefResolutionError(
            f"{ref_key} on {entity_key!r} must be a string $id, got {type(sid).__name__!r}."
        )

    try:
        return registry.resolve(sid)
    except RefResolutionError:
        raise RefResolutionError(
            f"Cannot resolve {ref_key}={sid!r} on entity {entity_key!r}. "
            "The referenced $id has not been registered yet — check processing order."
        ) from None


__all__ = ["resolve_item"]
