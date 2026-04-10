from Delivery_app_BK.errors import ValidationFailed


def validate_required(raw: dict, required: set[str], *, context_msg: str) -> None:
    missing = sorted(
        key for key in required if key not in raw or raw.get(key) is None
    )
    if missing:
        raise ValidationFailed(f"{context_msg} Missing required fields: {missing}.")


def validate_forbidden(
    raw: dict,
    forbidden: set[str] | list[str],
    *,
    context_msg: str,
) -> None:
    forbidden_keys = set(forbidden)
    found = sorted(key for key in forbidden_keys if key in raw)
    if found:
        raise ValidationFailed(f"{context_msg} {found}.")


def validate_unexpected(raw: dict, allowed: set[str], *, context_msg: str) -> None:
    unexpected = sorted(key for key in raw if key not in allowed)
    if unexpected:
        raise ValidationFailed(f"{context_msg} {unexpected}.")
