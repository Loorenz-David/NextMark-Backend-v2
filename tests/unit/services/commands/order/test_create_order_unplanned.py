import importlib
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.order.create_order import OrderCreateRequest


module = importlib.import_module("Delivery_app_BK.services.commands.order.create_order")

DISCARD_AFTER = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@contextmanager
def _tx():
    yield


class _DummySession:
    def begin(self):
        return _tx()

    def add_all(self, _instances):
        return None

    def flush(self):
        return None


def _build_ctx():
    return SimpleNamespace(
        set_relationship_map=lambda *_args, **_kwargs: None,
        team_id=1,
        identity={},
        user_id=None,
    )


def _build_request(*, delivery_plan_id=None, order_plan_objective=None):
    fields = {"client_id": "order_1"}
    if order_plan_objective is not None:
        fields["order_plan_objective"] = order_plan_objective
    return OrderCreateRequest(
        fields=fields,
        items=[],
        delivery_plan_id=delivery_plan_id,
        route_group_id=None,
        costumer=SimpleNamespace(
            costumer_id=4089,
            client_id=None,
            first_name=None,
            last_name=None,
            email=None,
            primary_phone=None,
            address=None,
        ),
        delivery_windows=[],
    )


def _patch_create_order(monkeypatch, request):
    created = []

    monkeypatch.setattr(module, "db", SimpleNamespace(session=_DummySession()))
    monkeypatch.setattr(module, "extract_fields", lambda _ctx: [{"idx": 0}])
    monkeypatch.setattr(module, "parse_create_order_request", lambda _raw: request)
    monkeypatch.setattr(module, "_load_route_plans_by_id", lambda _ctx, _ids: {})
    monkeypatch.setattr(
        module,
        "resolve_or_create_costumers",
        lambda _ctx, _inputs: [SimpleNamespace(id=4089)],
    )
    monkeypatch.setattr(module, "reserve_order_scalar_ids", lambda _ctx, _count: [1])
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "UTC")
    monkeypatch.setattr(module, "resolve_asserted_terms_version", lambda *_args: None)
    monkeypatch.setattr(module, "generate_tracking_identifiers", lambda _order: None)
    monkeypatch.setattr(module, "build_order_created_event", lambda _order: {})
    monkeypatch.setattr(module, "emit_order_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "serialize_created_order", lambda order: {"id": order.id})

    def _create_instance(_ctx, model, fields):
        if model is module.Order:
            order = SimpleNamespace(
                id=1,
                team_id=1,
                client_id=fields["client_id"],
                order_plan_objective=fields.get("order_plan_objective"),
                discard_after=None,
                items=[],
                delivery_windows=[],
                route_plan_id=None,
                route_plan=None,
                costumer_id=None,
                tracking_token_hash="hash",
                items_updated_at=None,
            )
            created.append(order)
            return order
        raise AssertionError(f"Unexpected model: {model}")

    monkeypatch.setattr(module, "create_instance", _create_instance)
    return created


def test_unplanned_order_keeps_null_objective_and_is_marked_for_discard(monkeypatch):
    created = _patch_create_order(monkeypatch, _build_request())

    module.create_order(_build_ctx(), unplanned_discard_after=DISCARD_AFTER)

    assert created[0].order_plan_objective is None
    assert created[0].discard_after == DISCARD_AFTER


def test_unplanned_order_ignores_a_requested_objective(monkeypatch):
    created = _patch_create_order(
        monkeypatch,
        _build_request(order_plan_objective="store_pickup"),
    )

    module.create_order(_build_ctx(), unplanned_discard_after=DISCARD_AFTER)

    assert created[0].order_plan_objective is None


def test_unplanned_order_cannot_be_created_into_a_plan(monkeypatch):
    _patch_create_order(monkeypatch, _build_request(delivery_plan_id=688))

    with pytest.raises(ValidationFailed):
        module.create_order(_build_ctx(), unplanned_discard_after=DISCARD_AFTER)


def test_regular_order_still_defaults_to_local_delivery(monkeypatch):
    created = _patch_create_order(monkeypatch, _build_request())

    module.create_order(_build_ctx())

    assert created[0].order_plan_objective == "local_delivery"
    assert created[0].discard_after is None
