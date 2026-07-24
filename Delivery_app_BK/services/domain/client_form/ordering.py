"""Position rules for the ordered client-form collections (rules and media)."""

from typing import Any, Dict, List, Sequence

from Delivery_app_BK.errors import ValidationFailed


def normalize_positions(ordered_ids: Sequence[Any]) -> List[Dict[str, Any]]:
    """Map an ordered id sequence onto a gapless 0..n-1 position sequence.

    Raises ValidationFailed when the sequence is empty or contains duplicates —
    both would produce an ambiguous ordering.
    """
    if not isinstance(ordered_ids, (list, tuple)):
        raise ValidationFailed("'ordered_ids' must be a list of ids.")
    if not ordered_ids:
        raise ValidationFailed("'ordered_ids' must contain at least one id.")

    seen = set()
    for target_id in ordered_ids:
        if not isinstance(target_id, (int, str)) or isinstance(target_id, bool):
            raise ValidationFailed("'ordered_ids' must contain integer or string ids.")
        if target_id in seen:
            raise ValidationFailed(f"Duplicate id '{target_id}' in 'ordered_ids'.")
        seen.add(target_id)

    return [
        {"target_id": target_id, "position": index}
        for index, target_id in enumerate(ordered_ids)
    ]


def next_position(current_positions: Sequence[int]) -> int:
    """Return the position to append at, given the positions already taken."""
    if not current_positions:
        return 0
    return max(current_positions) + 1
