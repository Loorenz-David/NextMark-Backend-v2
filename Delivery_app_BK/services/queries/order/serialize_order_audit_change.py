from Delivery_app_BK.models import OrderAuditLog

ITEM_STATE_FIELD = "item_state_id"


def serialize_order_audit_change(
    row: OrderAuditLog,
    labels_by_field: dict[str, dict[int, str]],
) -> dict:
    """`labels_by_field` names id-valued fields (item states, plans) so the
    history shows "Ready" or a plan's label rather than an id."""
    labels = labels_by_field.get(row.field_name, {})
    return {
        "id": row.id,
        "field_name": row.field_name,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "entity_label": row.entity_label,
        "from_value": row.from_value,
        "to_value": row.to_value,
        "from_label": labels.get(row.from_value) if isinstance(row.from_value, int) else None,
        "to_label": labels.get(row.to_value) if isinstance(row.to_value, int) else None,
    }
