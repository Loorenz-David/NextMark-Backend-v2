from Delivery_app_BK.errors import ValidationFailed


def guard_label_multiplier(fields: dict) -> None:
    """Ensure label_multiplier, when provided, is a positive integer.

    label_multiplier drives how many labels are printed per item, so a value of
    zero or less would produce no labels. The field is optional on create
    (defaults to 1) and on update, so absence is allowed; only a provided value
    is validated.
    """
    if "label_multiplier" not in fields:
        return

    value = fields.get("label_multiplier")

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationFailed("'label_multiplier' must be an integer.")
    if value < 1:
        raise ValidationFailed("'label_multiplier' must be greater than zero.")
