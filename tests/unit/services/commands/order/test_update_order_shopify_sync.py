from types import SimpleNamespace

from Delivery_app_BK.services.commands.order import update_order as module


def test_enqueue_shopify_customer_sync_jobs_dedupes_order_ids(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        module,
        "enqueue_job",
        lambda **kwargs: calls.append(kwargs),
    )

    order = SimpleNamespace(id=44)
    module._enqueue_shopify_customer_sync_jobs([order, order, SimpleNamespace(id=45), SimpleNamespace(id=None)])

    assert len(calls) == 2
    assert calls[0]["queue_key"] == "default"
    assert calls[0]["args"] == (44,)
    assert calls[1]["args"] == (45,)


def test_apply_order_updates_collects_shopify_sync_candidates(monkeypatch):
    order = SimpleNamespace(
        id=10,
        external_source="shopify",
        external_order_id="12345",
        costumer=SimpleNamespace(external_source=None, external_costumer_id=None),
        delivery_windows=[],
        delivery_plan=None,
        order_plan_objective=None,
        operation_type="dropoff",
        reference_number="ref",
        external_tracking_number=None,
        external_tracking_link=None,
        tracking_number=None,
        client_first_name="Old",
        client_last_name="Name",
        client_email="old@example.com",
        client_primary_phone=None,
        client_secondary_phone=None,
        client_address=None,
    )

    monkeypatch.setattr(module, "_resolve_orders_by_targets", lambda *_args, **_kwargs: {10: order})
    monkeypatch.setattr(module, "_build_mutable_fields", lambda raw_fields, existing_order: dict(raw_fields))
    monkeypatch.setattr(module, "_normalize_delivery_windows_for_update", lambda **_kwargs: None)
    monkeypatch.setattr(module, "_capture_sync_values", lambda _order: {})
    monkeypatch.setattr(
        module,
        "_capture_driver_visible_values",
        lambda current_order: {"client_email": current_order.client_email},
    )
    monkeypatch.setattr(
        module,
        "_resolve_changed_sections",
        lambda **_kwargs: ("details",),
    )
    monkeypatch.setattr(module, "_build_change_flags", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(module, "_resolve_delivery_plan_for_order", lambda _order: None)
    monkeypatch.setattr(module, "inject_fields", lambda ctx, existing, fields: setattr(existing, "client_email", fields["client_email"]))
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(
        module,
        "build_order_edited_event",
        lambda order_instance, changed_sections=None: {"order_id": order_instance.id, "payload": {"changed_sections": changed_sections}},
    )

    updated_orders, pending_events, order_deltas, shopify_sync_orders = module.apply_order_updates(
        SimpleNamespace(team_id=7),
        [
            {
                "target_id": 10,
                "fields": {"client_email": "new@example.com"},
            }
        ],
    )

    assert updated_orders == [order]
    assert len(pending_events) == 1
    assert len(order_deltas) == 1
    assert shopify_sync_orders == [order]
