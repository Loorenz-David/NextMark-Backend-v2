from datetime import datetime
from types import SimpleNamespace

import Delivery_app_BK.services.commands.order.create_serializers as create_module
import Delivery_app_BK.services.queries.order.serialize_order as list_module


def _build_order_instance():
    return SimpleNamespace(
        id=10,
        client_id="order_10",
        costumer_id=77,
        order_plan_objective=None,
        operation_type="dropoff",
        order_scalar_id=1,
        reference_number="REF-10",
        external_order_id=None,
        external_source=None,
        external_tracking_number=None,
        external_tracking_link=None,
        tracking_number=None,
        tracking_link=None,
        client_first_name="A",
        client_last_name="B",
        client_email="a@mail.com",
        client_primary_phone=None,
        client_secondary_phone=None,
        client_address=None,
        marketing_messages=False,
        creation_date=None,
        updated_at=None,
        items_updated_at=None,
        order_state_id=1,
        route_plan_id=42,
        route_group_id=7,
        delivery_plan_id=None,
        archive_at=None,
        order_cases=[],
        order_notes=None,
        client_form_submitted_at=None,
        total_weight_g=None,
        total_volume_cm3=None,
        total_item_count=None,
        delivery_windows=[
            SimpleNamespace(
                id=2,
                client_id="dw_2",
                start_at=datetime.fromisoformat("2026-03-05T12:00:00+00:00"),
                end_at=datetime.fromisoformat("2026-03-05T14:00:00+00:00"),
                window_type="FULL_RANGE",
            ),
            SimpleNamespace(
                id=1,
                client_id="dw_1",
                start_at=datetime.fromisoformat("2026-03-05T09:00:00+00:00"),
                end_at=datetime.fromisoformat("2026-03-05T11:00:00+00:00"),
                window_type="FULL_RANGE",
            ),
        ],
    )


def test_serialize_created_order_includes_costumer_id(monkeypatch):
    monkeypatch.setattr(create_module, "calculate_order_metrics", lambda _order: {})

    serialized = create_module.serialize_created_order(_build_order_instance())

    assert serialized["costumer_id"] == 77


def test_serialize_orders_includes_costumer_id(monkeypatch):
    monkeypatch.setattr(list_module, "calculate_order_metrics", lambda _order: {})
    monkeypatch.setattr(list_module, "map_return_values", lambda values, _ctx, _key: values)

    serialized = list_module.serialize_orders([_build_order_instance()], SimpleNamespace())

    assert serialized[0]["costumer_id"] == 77


def test_order_serializers_expose_canonical_route_fields(monkeypatch):
    monkeypatch.setattr(create_module, "calculate_order_metrics", lambda _order: {})
    monkeypatch.setattr(list_module, "calculate_order_metrics", lambda _order: {})
    monkeypatch.setattr(list_module, "map_return_values", lambda values, _ctx, _key: values)

    created = create_module.serialize_created_order(_build_order_instance())
    listed = list_module.serialize_orders([_build_order_instance()], SimpleNamespace())

    assert created["route_plan_id"] == 42
    assert created["route_group_id"] == 7
    assert "delivery_plan_id" not in created

    assert listed[0]["route_plan_id"] == 42
    assert listed[0]["route_group_id"] == 7
    assert "delivery_plan_id" not in listed[0]


def test_serializers_include_sorted_delivery_windows(monkeypatch):
    monkeypatch.setattr(create_module, "calculate_order_metrics", lambda _order: {})
    monkeypatch.setattr(list_module, "calculate_order_metrics", lambda _order: {})
    monkeypatch.setattr(list_module, "map_return_values", lambda values, _ctx, _key: values)

    created = create_module.serialize_created_order(_build_order_instance())
    listed = list_module.serialize_orders([_build_order_instance()], SimpleNamespace())

    assert created["delivery_windows"][0]["client_id"] == "dw_1"
    assert created["delivery_windows"][1]["client_id"] == "dw_2"
    assert listed[0]["delivery_windows"][0]["client_id"] == "dw_1"
