from Delivery_app_BK.services.domain.order.order_events import (
    ORDER_EVENT_ORIGIN_CLIENT,
    ORDER_EVENT_ORIGIN_SYSTEM,
    ORDER_EVENT_ORIGIN_USER,
    resolve_order_event_origin,
)


def test_public_form_events_are_the_clients():
    assert resolve_order_event_origin("client_form_submitted", {}, None) == ORDER_EVENT_ORIGIN_CLIENT
    assert (
        resolve_order_event_origin(
            "order_edited", {"changed_sections": ["client_form_submission"]}, None
        )
        == ORDER_EVENT_ORIGIN_CLIENT
    )


def test_linked_device_submission_is_the_clients_even_with_a_relaying_user():
    payload = {
        "changed_sections": ["client_form_submission"],
        "submission_source": "linked_device",
        "relayed_by_user_id": 5,
    }

    assert resolve_order_event_origin("order_edited", payload, None) == ORDER_EVENT_ORIGIN_CLIENT


def test_staff_edit_is_the_users():
    assert (
        resolve_order_event_origin("order_edited", {"changed_sections": ["customer"]}, 5)
        == ORDER_EVENT_ORIGIN_USER
    )


def test_integration_edit_without_actor_is_the_systems():
    assert (
        resolve_order_event_origin(
            "order_edited", {"changed_sections": ["shopify_customer_sync"]}, None
        )
        == ORDER_EVENT_ORIGIN_SYSTEM
    )
