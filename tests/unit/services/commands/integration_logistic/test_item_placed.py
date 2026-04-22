import importlib
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.services.requests.integration_logistic.item_placed_request import (
    ItemPlacedRequest,
    LogisticLocationPayload,
)


module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_logistic.inbound.item_placed"
)


def _request() -> ItemPlacedRequest:
    return ItemPlacedRequest(
        event="item_placed",
        shop_id="shop-1",
        scan_history_id="scan-1",
        order_id="external-order-1",
        item_sku="SKU-1",
        logistic_location=LogisticLocationPayload(
            id="loc-1",
            location="Shelf A-3",
            updated_at="2026-04-22T10:30:00Z",
        ),
    )


def test_item_placed_updates_matching_items_and_emits_event(monkeypatch):
    order = SimpleNamespace(id=10, team_id=7)
    items = [SimpleNamespace(item_position=None), SimpleNamespace(item_position=None)]
    emitted_events: list[dict] = []
    built_events: list[dict] = []
    query_results = [
        SimpleNamespace(filter=lambda *args, **kwargs: SimpleNamespace(first=lambda: order)),
        SimpleNamespace(filter=lambda *args, **kwargs: SimpleNamespace(all=lambda: items)),
    ]

    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: query_results.pop(0),
    )
    monkeypatch.setattr(module.db.session, "commit", lambda: emitted_events.append({"commit": True}))
    monkeypatch.setattr(
        module,
        "build_order_edited_event",
        lambda order_instance, changed_sections=None: built_events.append(
            {"order": order_instance, "changed_sections": changed_sections}
        )
        or {"event_name": "order.edited"},
    )
    monkeypatch.setattr(
        module,
        "emit_order_events",
        lambda ctx, events: emitted_events.append({"team_id": ctx.team_id, "events": events}),
    )

    result = module.item_placed(_request())

    assert result == {"updated_count": 2}
    assert [item.item_position for item in items] == ["Shelf A-3", "Shelf A-3"]
    assert built_events == [{"order": order, "changed_sections": ["items"]}]
    assert emitted_events[-1] == {"team_id": 7, "events": [{"event_name": "order.edited"}]}


def test_item_placed_returns_warning_when_no_matching_items(monkeypatch):
    order = SimpleNamespace(id=10, team_id=7)
    query_results = [
        SimpleNamespace(filter=lambda *args, **kwargs: SimpleNamespace(first=lambda: order)),
        SimpleNamespace(filter=lambda *args, **kwargs: SimpleNamespace(all=lambda: [])),
    ]
    emit_calls: list[dict] = []

    monkeypatch.setattr(module.db.session, "query", lambda _model: query_results.pop(0))
    monkeypatch.setattr(module.db.session, "commit", lambda: emit_calls.append({"commit": True}))
    monkeypatch.setattr(module, "emit_order_events", lambda *args, **kwargs: emit_calls.append(kwargs))

    result = module.item_placed(_request())

    assert result == {
        "updated_count": 0,
        "warning": "No items found for SKU 'SKU-1' in order 'external-order-1'",
    }
    assert emit_calls == []


def test_item_placed_raises_when_order_cannot_be_resolved(monkeypatch):
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: SimpleNamespace(filter=lambda *args, **kwargs: SimpleNamespace(first=lambda: None)),
    )

    with pytest.raises(NotFound):
        module.item_placed(_request())
