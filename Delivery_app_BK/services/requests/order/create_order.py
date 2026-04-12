from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.item.item_states import ItemStateId
from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from Delivery_app_BK.services.requests.common.fields import (
    validate_forbidden,
    validate_unexpected,
)
from Delivery_app_BK.services.requests.common.types import (
    parse_client_id,
    parse_optional_dict,
    parse_optional_int,
    parse_optional_json,
    parse_optional_string,
    parse_required_bool,
    parse_required_int,
    validate_str,
)


ORDER_ALLOWED_FIELDS = {
    "client_id",
    "costumer",
    "order_plan_objective",
    "reference_number",
    "external_order_id",
    "external_source",
    "external_tracking_number",
    "external_tracking_link",
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
    "marketing_messages",
    "delivery_windows",
    "order_state_id",
    "delivery_plan_id",
    "items",
    "operation_type",
    "order_notes",
}

ORDER_FORBIDDEN_FIELDS = {
    "id",
    "team_id",
    "state",
    "state_history",
    "events",
    "order_cases",
    "delivery_plan",
    "team",
}

ITEM_ALLOWED_FIELDS = {
    "client_id",
    "article_number",
    "reference_number",
    "item_type",
    "properties",
    "quantity",
    "item_position_id",
    "item_state_id",
    "page_link",
    "dimension_depth",
    "dimension_height",
    "dimension_width",
    "weight",
}

ITEM_FORBIDDEN_FIELDS = {
    "id",
    "team_id",
    "order_id",
}

ORDER_OPTIONAL_STRING_FIELDS = {
    "order_plan_objective",
    "operation_type",
    "reference_number",
    "external_order_id",
    "external_source",
    "external_tracking_number",
    "external_tracking_link",
    "client_first_name",
    "client_last_name",
    "client_email",
}

ITEM_OPTIONAL_STRING_FIELDS = {
    "reference_number",
    "item_type",
    "page_link",
}

ITEM_OPTIONAL_INT_FIELDS = {
    "quantity",
    "item_position_id",
    "item_state_id",
    "dimension_depth",
    "dimension_height",
    "dimension_width",
    "weight",
}

ORDER_OBJECTIVES = {
    "local_delivery",
    "international_shipping",
    "store_pickup",
}

ORDER_OPERATION_TYPES ={
        "pickup",
        "dropoff",
        "pickup_dropoff",
}

COSTUMER_ALLOWED_FIELDS = {
    "costumer_id",
    "client_id",
    "first_name",
    "last_name",
    "email",
    "primary_phone",
    "address",
}


@dataclass
class ItemCreateRequest:
    fields: dict


@dataclass
class OrderCostumerRequest:
    costumer_id: int | None
    client_id: str | None
    first_name: str | None
    last_name: str | None
    email: str | None
    primary_phone: dict | None
    address: dict | None


@dataclass
class OrderCreateRequest:
    fields: dict
    items: list[ItemCreateRequest]
    delivery_plan_id: int | None
    costumer: OrderCostumerRequest | None
    delivery_windows: list[dict] | None = None


def parse_create_order_request(raw_fields: dict) -> OrderCreateRequest:
    if not isinstance(raw_fields, dict):
        raise ValidationFailed("Each create payload in 'fields' must be an object.")

    validate_forbidden(
        raw_fields,
        ORDER_FORBIDDEN_FIELDS,
        context_msg="Forbidden fields in order create payload:",
    )
    validate_unexpected(
        raw_fields,
        ORDER_ALLOWED_FIELDS,
        context_msg="Unexpected fields in order create payload:",
    )

    order_fields: dict = {
        "client_id": parse_client_id(raw_fields.get("client_id"), prefix="order"),
        "order_state_id": _parse_order_state_id(raw_fields.get("order_state_id")),
    }

    delivery_plan_id = _parse_delivery_plan_id(raw_fields.get("delivery_plan_id"))
    if delivery_plan_id is not None:
        order_fields["delivery_plan_id"] = delivery_plan_id
    costumer = _parse_costumer(raw_fields.get("costumer"))

    for field in ORDER_OPTIONAL_STRING_FIELDS:
        if field in raw_fields:
            parsed_value = parse_optional_string(
                raw_fields.get(field),
                field=field,
            )
            if field == "order_plan_objective" and parsed_value:
                if parsed_value not in ORDER_OBJECTIVES:
                    raise ValidationFailed(
                        f"Invalid order_plan_objective: {parsed_value}"
                    )
            elif field == "operation_type" and parsed_value:
                if parsed_value not in ORDER_OPERATION_TYPES:
                    raise ValidationFailed(
                        f"Invalid order_operation type: {parsed_value}"
                    )
                
            order_fields[field] = parsed_value

    if "client_primary_phone" in raw_fields:
        order_fields["client_primary_phone"] = parse_optional_dict(
            raw_fields.get("client_primary_phone"),
            field="client_primary_phone",
        )

    if "client_secondary_phone" in raw_fields:
        order_fields["client_secondary_phone"] = parse_optional_dict(
            raw_fields.get("client_secondary_phone"),
            field="client_secondary_phone",
        )

    if "client_address" in raw_fields:
        order_fields["client_address"] = parse_optional_dict(
            raw_fields.get("client_address"),
            field="client_address",
        )

    if "marketing_messages" in raw_fields:
        order_fields["marketing_messages"] = parse_required_bool(
            raw_fields.get("marketing_messages"),
            field="marketing_messages",
        )

    item_requests = _parse_items(raw_fields)
    delivery_windows = _parse_delivery_windows(raw_fields)
    return OrderCreateRequest(
        fields=order_fields,
        items=item_requests,
        delivery_plan_id=delivery_plan_id,
        costumer=costumer,
        delivery_windows=delivery_windows,
    )


def _parse_items(raw_fields: dict) -> list[ItemCreateRequest]:
    if "items" not in raw_fields:
        return []

    items_payload = raw_fields.get("items")
    if not isinstance(items_payload, list):
        raise ValidationFailed("items must be a list of objects.")

    return [_parse_item(item_raw, index) for index, item_raw in enumerate(items_payload)]


def _parse_delivery_windows(raw_fields: dict) -> list[dict] | None:
    if "delivery_windows" not in raw_fields:
        return None

    payload = raw_fields.get("delivery_windows")
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValidationFailed("delivery_windows must be a list of objects.")

    parsed_rows: list[dict] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValidationFailed(f"delivery_windows[{index}] must be an object.")

        if "start_at" not in row:
            raise ValidationFailed(f"delivery_windows[{index}].start_at is required.")
        if "end_at" not in row:
            raise ValidationFailed(f"delivery_windows[{index}].end_at is required.")
        if "window_type" not in row:
            raise ValidationFailed(f"delivery_windows[{index}].window_type is required.")

        parsed_rows.append(
            {
                "client_id": parse_optional_string(
                    row.get("client_id"),
                    field=f"delivery_windows[{index}].client_id",
                )
                if "client_id" in row
                else None,
                "start_at": row.get("start_at"),
                "end_at": row.get("end_at"),
                "window_type": parse_optional_string(
                    row.get("window_type"),
                    field=f"delivery_windows[{index}].window_type",
                ),
            }
        )

    return parsed_rows


def _parse_item(item_raw, index: int) -> ItemCreateRequest:
    if not isinstance(item_raw, dict):
        raise ValidationFailed(f"items[{index}] must be an object.")

    if "order_id" in item_raw:
        raise ValidationFailed("items[].order_id is not allowed in nested order create.")

    validate_forbidden(
        item_raw,
        ITEM_FORBIDDEN_FIELDS,
        context_msg="Forbidden fields in items payload:",
    )
    validate_unexpected(
        item_raw,
        ITEM_ALLOWED_FIELDS,
        context_msg="Unexpected fields in items payload:",
    )

    item_fields: dict = {
        "client_id": parse_client_id(item_raw.get("client_id"), prefix="item"),
        "item_state_id": _parse_item_state_id(item_raw.get("item_state_id")),
        "article_number": validate_str(
            item_raw.get("article_number"),
            field=f"items[{index}].article_number",
        ),
    }

    for field in ITEM_OPTIONAL_STRING_FIELDS:
        if field in item_raw:
            item_fields[field] = parse_optional_string(
                item_raw.get(field),
                field=f"items[{index}].{field}",
            )

    for field in ITEM_OPTIONAL_INT_FIELDS:
        if field in item_raw:
            item_fields[field] = parse_optional_int(
                item_raw.get(field),
                field=f"items[{index}].{field}",
            )

    if "properties" in item_raw:
        item_fields["properties"] = parse_optional_json(
            item_raw.get("properties"),
            field=f"items[{index}].properties",
        )

    return ItemCreateRequest(fields=item_fields)


def _parse_order_state_id(value) -> int:
    if value is None:
        return OrderStateId.DRAFT
    return parse_required_int(value, field="order_state_id")


def _parse_item_state_id(value) -> int:
    if value is None:
        return ItemStateId.OPEN
    return parse_required_int(value, field="item_state_id")


def _parse_delivery_plan_id(value) -> int | None:
    if value is None:
        return None
    return parse_required_int(value, field="delivery_plan_id")


def _parse_costumer_id(value) -> int | None:
    if value is None:
        return None
    return parse_required_int(value, field="costumer_id")


def _parse_costumer(value) -> OrderCostumerRequest | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationFailed("costumer must be an object.")

    validate_unexpected(
        value,
        COSTUMER_ALLOWED_FIELDS,
        context_msg="Unexpected fields in costumer payload:",
    )

    return OrderCostumerRequest(
        costumer_id=_parse_costumer_id(value.get("costumer_id")),
        client_id=parse_optional_string(value.get("client_id"), field="costumer.client_id"),
        first_name=parse_optional_string(value.get("first_name"), field="costumer.first_name"),
        last_name=parse_optional_string(value.get("last_name"), field="costumer.last_name"),
        email=parse_optional_string(value.get("email"), field="costumer.email"),
        primary_phone=parse_optional_dict(value.get("primary_phone"), field="costumer.primary_phone"),
        address=parse_optional_dict(value.get("address"), field="costumer.address"),
    )
