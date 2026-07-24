"""Rules governing terms-and-conditions versions and customer acceptance.

Terms versions are immutable: publishing never edits an existing row, it appends
a new one and moves the active flag. These helpers hold the invariants that
decision depends on.
"""

from typing import Any, Optional

from Delivery_app_BK.errors import ValidationFailed


def next_version_number(current_version_number: Optional[int]) -> int:
    """Return the version number for the next published version."""
    if current_version_number is None:
        return 1
    if not isinstance(current_version_number, int) or isinstance(current_version_number, bool):
        raise ValidationFailed("Current terms version number must be an integer.")
    if current_version_number < 1:
        raise ValidationFailed("Current terms version number must be positive.")
    return current_version_number + 1


def validate_terms_content(content: Any) -> Any:
    """Terms content is a rich-text document — a JSON object or array, never empty."""
    if content is None:
        raise ValidationFailed("Terms content is required to publish a version.")
    if not isinstance(content, (dict, list)):
        raise ValidationFailed("Terms content must be a JSON object or array.")
    if not content:
        raise ValidationFailed("Terms content cannot be empty.")
    return content


def requires_acceptance(settings: Any) -> bool:
    """True when a submission must carry an accepted terms version to be valid."""
    if settings is None:
        return False
    return bool(getattr(settings, "terms_enabled", False)) and bool(
        getattr(settings, "require_acceptance", False)
    )
