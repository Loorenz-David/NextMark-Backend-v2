from types import SimpleNamespace

from Delivery_app_BK.sockets import notifications as module


def _row(field_name, from_value, to_value):
    return SimpleNamespace(
        field_name=field_name,
        from_value=from_value,
        to_value=to_value,
        entity_type="order",
        entity_id=None,
        entity_label=None,
    )


def test_staff_update_description_lists_what_changed():
    description = module._build_order_updated_description(
        order_label="Order #2549",
        payload={
            "notification_origin": "user",
            "notification_change_labels": ["Email", "Address", "Phone", "Customer note"],
            "changed_sections": ["details"],
        },
    )

    assert description == "Order #2549 updated: Email, Address and 2 more."


def test_update_without_recorded_changes_falls_back_to_sections():
    description = module._build_order_updated_description(
        order_label="Order #2549",
        payload={
            "notification_origin": "user",
            "notification_change_labels": [],
            "changed_sections": ["details", "items"],
        },
    )

    assert description == "Order #2549 details and items were updated."


def test_client_submission_description_names_the_client():
    with_changes = module._build_order_updated_description(
        order_label="Order #2549",
        payload={
            "notification_origin": "client",
            "notification_change_labels": ["Email"],
        },
    )
    without_changes = module._build_order_updated_description(
        order_label="Order #2549",
        payload={"changed_sections": ["client_form_submission"]},
    )

    assert with_changes == "Client submitted the form for Order #2549 and updated Email."
    # The realtime preview has no resolved origin; it is derived from the payload.
    assert without_changes == "Client submitted the form for Order #2549."


def test_change_labels_are_read_from_the_submission_event_and_skip_first_fills(monkeypatch):
    calls = []

    def fake_list(**kwargs):
        calls.append(kwargs)
        return [_row("client_email", None, "a@x.com"), _row("client_last_name", "Doe", "Roe")]

    monkeypatch.setattr(module, "list_order_event_audit_changes", fake_list)

    labels = module._resolve_order_change_labels(
        event_name="order.updated",
        event_id="edit-event",
        team_id=7,
        order_id=14,
        payload={"audit_event_id": "submission-event"},
        origin="client",
    )

    assert calls == [{"team_id": 7, "order_id": 14, "event_id": "submission-event"}]
    assert labels == ["Last name"]


def test_change_labels_use_the_event_itself_for_staff_edits(monkeypatch):
    calls = []

    def fake_list(**kwargs):
        calls.append(kwargs)
        return [_row("client_email", None, "a@x.com")]

    monkeypatch.setattr(module, "list_order_event_audit_changes", fake_list)

    labels = module._resolve_order_change_labels(
        event_name="order.updated",
        event_id="edit-event",
        team_id=7,
        order_id=14,
        payload={},
        origin="user",
    )

    assert calls[0]["event_id"] == "edit-event"
    assert labels == ["Email"]


def test_change_labels_are_only_loaded_for_updates(monkeypatch):
    monkeypatch.setattr(
        module,
        "list_order_event_audit_changes",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not query")),
    )

    assert module._resolve_order_change_labels(
        event_name="order.state_changed",
        event_id="e",
        team_id=7,
        order_id=14,
        payload={},
        origin="user",
    ) == []


def test_notification_item_carries_actor_subject_and_truncated_changes():
    actor = SimpleNamespace(id=5, username="david", email=None)

    item = module.build_notification_item(
        event_id="e",
        recipient_user_id=9,
        app_scope="admin",
        kind="order.updated",
        entity_type="order",
        entity_id=14,
        team_id=7,
        actor=actor,
        actor_role="Dispatcher",
        title="Order updated",
        description="Order #2549 updated: Email, Address and 3 more.",
        occurred_at="2026-10-07T10:00:00+00:00",
        target={"kind": "order_detail"},
        subject_label="Order #2549",
        change_labels=["Email", "Address", "Phone", "Note", "Window"],
    )

    assert item["actor_kind"] == "user"
    assert item["actor_role"] == "Dispatcher"
    assert item["subject_label"] == "Order #2549"
    assert item["change_labels"] == ["Email", "Address", "Phone"]
    assert item["change_count"] == 5


def test_notification_item_without_actor_is_the_systems():
    item = module.build_notification_item(
        event_id="e",
        recipient_user_id=9,
        app_scope="admin",
        kind="route_plan.updated",
        entity_type="delivery_plan",
        entity_id=3,
        team_id=7,
        actor=None,
        title="Route plan updated",
        description="Route plan was updated.",
        occurred_at="2026-10-07T10:00:00+00:00",
        target={"kind": "local_delivery_workspace"},
    )

    assert item["actor_kind"] == "system"
    assert item["actor_role"] is None
    assert "subject_label" not in item
    assert "change_labels" not in item


def test_client_update_title():
    assert module._build_order_notification_title("order.updated", "client") == "Client form submitted"
    assert module._build_order_notification_title("order.updated", "user") == "Order updated"


def _order_target(event_name, order_event_id):
    return module._build_notification_target(
        app_scope="admin",
        event_name=event_name,
        order=SimpleNamespace(id=14),
        payload={},
        route_id=None,
        entity_type="order",
        entity_id=14,
        order_event_id=order_event_id,
    )


def test_update_notifications_focus_the_event_and_client_ones_their_submission():
    staff = module._resolve_order_focus_event_id(
        event_name="order.updated", event_id="edit-event", payload={}
    )
    client = module._resolve_order_focus_event_id(
        event_name="order.updated",
        event_id="edit-event",
        payload={"audit_event_id": "submission-event"},
    )
    status = module._resolve_order_focus_event_id(
        event_name="order.state_changed", event_id="status-event", payload={}
    )

    assert (staff, client, status) == ("edit-event", "submission-event", "status-event")
    assert _order_target("order.updated", client)["params"] == {
        "orderId": 14,
        "orderEventId": "submission-event",
    }


def test_created_notifications_open_the_order_without_focusing_an_event():
    focus = module._resolve_order_focus_event_id(
        event_name="order.created", event_id="created-event", payload={}
    )

    assert focus is None
    assert _order_target("order.created", focus)["params"] == {"orderId": 14}
