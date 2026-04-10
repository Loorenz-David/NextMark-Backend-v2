from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import InvalidRequestError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import (
    Costumer,
    Facility,
    ItemProperty,
    ItemType,
    Order,
    RoutePlan,
    Vehicle,
    db,
)
from Delivery_app_BK.services.context import ServiceContext

TEST_PLAN_LABELS: dict[str, set[str]] = {}


def clear_generated_test_data(ctx: ServiceContext) -> dict[str, Any]:
    """Delete seeded test data in an idempotent way for the current team."""
    team_id = ctx.team_id
    if not isinstance(team_id, int) or team_id <= 0:
        raise ValidationFailed("team_id is required to clean test data.")

    incoming_data = ctx.incoming_data if isinstance(ctx.incoming_data, dict) else {}
    reference_prefix = _resolve_prefix(
        incoming_data.get("order_reference_prefix"),
        default="test-",
        field_name="order_reference_prefix",
    )
    name_prefix = _resolve_prefix(
        incoming_data.get("item_name_prefix"),
        default="test-",
        field_name="item_name_prefix",
    )
    extra_plan_labels = _parse_optional_string_list(
        incoming_data.get("additional_plan_labels"),
        field_name="additional_plan_labels",
    )
    client_id_prefix = _resolve_prefix(
        incoming_data.get("client_id_prefix"),
        default="td:",
        field_name="client_id_prefix",
    )

    plan_labels = set(extra_plan_labels)
    for labels in TEST_PLAN_LABELS.values():
        plan_labels.update(labels)

    result: dict[str, Any] = {}

    def _apply() -> None:
        plan_ids = _load_test_plan_ids(team_id=team_id, plan_labels=plan_labels)
        order_ids = _load_test_order_ids(
            team_id=team_id,
            plan_ids=plan_ids,
            reference_prefix=reference_prefix,
            client_id_prefix=client_id_prefix,
        )

        deleted_orders = _delete_orders(team_id, plan_ids, reference_prefix, client_id_prefix)
        deleted_plans = _delete_delivery_plans(team_id, plan_ids, client_id_prefix)
        deleted_facilities = _delete_facilities(team_id, client_id_prefix)
        deleted_vehicles = _delete_vehicles(team_id, client_id_prefix)
        deleted_item_types = _delete_item_types(team_id, name_prefix, client_id_prefix)
        deleted_item_properties = _delete_item_properties(team_id, name_prefix, client_id_prefix)
        deleted_costumers = _delete_costumers(team_id, client_id_prefix)

        result.update(
            {
                "team_id": team_id,
                "matched_plan_count": len(plan_ids),
                "matched_order_count": len(order_ids),
                "deleted_orders": deleted_orders,
                "deleted_delivery_plans": deleted_plans,
                "deleted_facilities": deleted_facilities,
                "deleted_vehicles": deleted_vehicles,
                "deleted_item_types": deleted_item_types,
                "deleted_item_properties": deleted_item_properties,
                "deleted_costumers": deleted_costumers,
                "reference_prefix": reference_prefix,
                "item_name_prefix": name_prefix,
                "additional_plan_labels": extra_plan_labels,
                "client_id_prefix": client_id_prefix,
            }
        )

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()

    return result


def _load_test_plan_ids(*, team_id: int, plan_labels: set[str]) -> list[int]:
    if not plan_labels:
        return []
    rows = (
        db.session.query(RoutePlan.id)
        .filter(RoutePlan.team_id == team_id)
        .filter(RoutePlan.label.in_(sorted(plan_labels)))
        .all()
    )
    return [row[0] for row in rows]


def _load_test_order_ids(
    *,
    team_id: int,
    plan_ids: list[int],
    reference_prefix: str,
    client_id_prefix: str,
) -> list[int]:
    query = db.session.query(Order.id).filter(Order.team_id == team_id)
    conditions = []
    if plan_ids:
        conditions.append(Order.route_plan_id.in_(plan_ids))
    if reference_prefix:
        conditions.append(Order.reference_number.like(f"{reference_prefix}%"))
    if client_id_prefix:
        conditions.append(Order.client_id.like(f"{client_id_prefix}%"))
    if not conditions:
        return []

    rows = query.filter(or_(*conditions)).all()
    return [row[0] for row in rows]


def _delete_orders(
    team_id: int,
    plan_ids: list[int],
    reference_prefix: str,
    client_id_prefix: str,
) -> int:
    query = db.session.query(Order).filter(Order.team_id == team_id)
    conditions = []
    if plan_ids:
        conditions.append(Order.route_plan_id.in_(plan_ids))
    if reference_prefix:
        conditions.append(Order.reference_number.like(f"{reference_prefix}%"))
    if client_id_prefix:
        conditions.append(Order.client_id.like(f"{client_id_prefix}%"))
    if not conditions:
        return 0
    return query.filter(or_(*conditions)).delete(synchronize_session=False)


def _delete_delivery_plans(team_id: int, plan_ids: list[int], client_id_prefix: str) -> int:
    conditions = []
    if plan_ids:
        conditions.append(RoutePlan.id.in_(plan_ids))
    if client_id_prefix:
        conditions.append(RoutePlan.client_id.like(f"{client_id_prefix}%"))
    if not conditions:
        return 0

    return db.session.query(RoutePlan).filter(RoutePlan.team_id == team_id).filter(
        or_(*conditions)
    ).delete(synchronize_session=False)


def _delete_facilities(team_id: int, client_id_prefix: str) -> int:
    if not client_id_prefix:
        return 0
    return (
        db.session.query(Facility)
        .filter(Facility.team_id == team_id)
        .filter(Facility.client_id.like(f"{client_id_prefix}%"))
        .delete(synchronize_session=False)
    )


def _delete_vehicles(team_id: int, client_id_prefix: str) -> int:
    if not client_id_prefix:
        return 0
    return (
        db.session.query(Vehicle)
        .filter(Vehicle.team_id == team_id)
        .filter(Vehicle.client_id.like(f"{client_id_prefix}%"))
        .delete(synchronize_session=False)
    )


def _delete_item_types(team_id: int, name_prefix: str, client_id_prefix: str) -> int:
    conditions = []
    if name_prefix:
        conditions.append(ItemType.name.like(f"{name_prefix}%"))
    if client_id_prefix:
        conditions.append(ItemType.client_id.like(f"{client_id_prefix}%"))
    if not conditions:
        return 0
    return db.session.query(ItemType).filter(ItemType.team_id == team_id).filter(
        or_(*conditions)
    ).delete(synchronize_session=False)


def _delete_item_properties(team_id: int, name_prefix: str, client_id_prefix: str) -> int:
    conditions = []
    if name_prefix:
        conditions.append(ItemProperty.name.like(f"{name_prefix}%"))
    if client_id_prefix:
        conditions.append(ItemProperty.client_id.like(f"{client_id_prefix}%"))
    if not conditions:
        return 0
    return db.session.query(ItemProperty).filter(ItemProperty.team_id == team_id).filter(
        or_(*conditions)
    ).delete(synchronize_session=False)


def _delete_costumers(team_id: int, client_id_prefix: str) -> int:
    if not client_id_prefix:
        return 0
    return (
        db.session.query(Costumer)
        .filter(Costumer.team_id == team_id)
        .filter(Costumer.client_id.like(f"{client_id_prefix}%"))
        .delete(synchronize_session=False)
    )


def _resolve_prefix(value: Any, *, default: str, field_name: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValidationFailed(f"{field_name} must be a string.")
    return value.strip()


def _parse_optional_string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed(f"{field_name} must be a list of strings.")

    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValidationFailed(
                f"{field_name}[{index}] must be a non-empty string."
            )
        output.append(item.strip())
    return output


__all__ = ["clear_generated_test_data"]
