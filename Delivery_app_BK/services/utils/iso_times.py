from datetime import datetime, timezone
from Delivery_app_BK.errors import ValidationFailed


def to_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        # Ensure UTC
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")

            dt = datetime.fromisoformat(value)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except Exception:
            raise ValidationFailed("Date values must be ISO format")

    raise ValidationFailed("Date values must be ISO format")