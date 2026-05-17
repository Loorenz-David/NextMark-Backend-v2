from types import SimpleNamespace

from Delivery_app_BK.sockets.emitters.route_solution_stop_events import _build_stop_client_label
from Delivery_app_BK.sockets.notifications import _build_order_label


def test_order_notification_label_uses_external_reference_when_external_source_is_set():
    order = SimpleNamespace(
        id=7,
        order_scalar_id=101,
        external_source="shopify",
        reference_number="#5001",
    )

    assert _build_order_label(order) == "Order #5001"


def test_order_notification_label_uses_scalar_id_for_internal_orders():
    order = SimpleNamespace(
        id=7,
        order_scalar_id=101,
        external_source=None,
        reference_number="#5001",
    )

    assert _build_order_label(order) == "Order #101"


def test_route_stop_client_label_uses_external_reference_without_client_name():
    order = SimpleNamespace(
        client_first_name=None,
        client_last_name=None,
        order_scalar_id=101,
        external_source="shopify",
        reference_number="#5001",
    )

    assert _build_stop_client_label(order) == "Order #5001"
