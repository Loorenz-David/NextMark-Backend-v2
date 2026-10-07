from Delivery_app_BK.models import OrderAuditLog

ITEM_STATE_FIELD = "item_state_id"


def serialize_order_audit_change(
    row: OrderAuditLog,
    item_state_names_by_id: dict[int, str],
) -> dict:
    is_item_state = row.field_name == ITEM_STATE_FIELD
    return {
        "id": row.id,
        "field_name": row.field_name,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "entity_label": row.entity_label,
        "from_value": row.from_value,
        "to_value": row.to_value,
        "from_label": item_state_names_by_id.get(row.from_value) if is_item_state else None,
        "to_label": item_state_names_by_id.get(row.to_value) if is_item_state else None,
    }
