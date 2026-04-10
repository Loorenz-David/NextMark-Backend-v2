from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order import update_order_notes as module
from Delivery_app_BK.services.context import ServiceContext


def test_update_order_notes_updates_general_note_and_emits_event(monkeypatch):
    order = SimpleNamespace(
        id=4360,
        team_id=7,
        order_notes=[
            {"type": "GENERAL", "content": "old general"},
            {"type": "FAILURE", "content": "keep"},
        ],
    )
    emitted_events: list[dict] = []

    monkeypatch.setattr(module, "get_instance", lambda **kwargs: order)
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: emitted_events.extend(events))
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    result = module.update_order_notes(
        ServiceContext(
            incoming_data={
                "target_id": 4360,
                "order_notes": {"type": "GENERAL", "content": "some new general notes"},
            },
            identity={"team_id": 7, "active_team_id": 7},
        ),
        "update",
    )

    assert result["order_notes"] == [
        {"type": "GENERAL", "content": "some new general notes"},
        {"type": "FAILURE", "content": "keep"},
    ]
    assert order.order_notes == result["order_notes"]
    assert len(emitted_events) == 1
    assert emitted_events[0]["order_id"] == 4360
    assert emitted_events[0]["payload"]["changed_sections"] == ["details"]


def test_update_order_notes_updates_costumer_note_from_stringified_list_entry(monkeypatch):
    order = SimpleNamespace(
        id=4360,
        team_id=7,
        order_notes=[
            "{\"type\": \"COSTUMER\", \"content\": \"old client note\"}",
        ],
    )

    monkeypatch.setattr(module, "get_instance", lambda **kwargs: order)
    monkeypatch.setattr(module, "emit_order_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    result = module.update_order_notes(
        ServiceContext(
            incoming_data={
                "target_id": 4360,
                "order_notes": {"type": "COSTUMER", "content": "new client note"},
            },
            identity={"team_id": 7, "active_team_id": 7},
        ),
        "update",
    )

    assert result["order_notes"] == [{"type": "COSTUMER", "content": "new client note"}]


def test_update_order_notes_rejects_non_editable_note_type(monkeypatch):
    order = SimpleNamespace(id=4360, team_id=7, order_notes=[{"type": "FAILURE", "content": "x"}])

    monkeypatch.setattr(module, "get_instance", lambda **kwargs: order)

    with pytest.raises(ValidationFailed):
        module.update_order_notes(
            ServiceContext(
                incoming_data={
                    "target_id": 4360,
                    "order_notes": {"type": "FAILURE", "content": "new"},
                },
                identity={"team_id": 7, "active_team_id": 7},
            ),
            "update",
        )


def test_delete_order_notes_deletes_matching_note(monkeypatch):
    order = SimpleNamespace(
        id=4360,
        team_id=7,
        order_notes=[
            {"type": "GENERAL", "content": "remove me"},
            {"type": "FAILURE", "content": "keep"},
        ],
    )

    monkeypatch.setattr(module, "get_instance", lambda **kwargs: order)
    monkeypatch.setattr(module, "emit_order_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "add", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)

    result = module.update_order_notes(
        ServiceContext(
            incoming_data={
                "target_id": 4360,
                "order_notes": {"type": "GENERAL", "content": "remove me"},
            },
            identity={"team_id": 7, "active_team_id": 7},
        ),
        "delete",
    )

    assert result["order_notes"] == [{"type": "FAILURE", "content": "keep"}]


def test_delete_order_notes_rejects_missing_match(monkeypatch):
    order = SimpleNamespace(id=4360, team_id=7, order_notes=[{"type": "GENERAL", "content": "keep"}])

    monkeypatch.setattr(module, "get_instance", lambda **kwargs: order)

    with pytest.raises(ValidationFailed):
        module.update_order_notes(
            ServiceContext(
                incoming_data={
                    "target_id": 4360,
                    "order_notes": {"type": "GENERAL", "content": "missing"},
                },
                identity={"team_id": 7, "active_team_id": 7},
            ),
            "delete",
        )
