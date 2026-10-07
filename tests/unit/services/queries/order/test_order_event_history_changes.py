from types import SimpleNamespace

from Delivery_app_BK.services.queries.order import get_order_event_history as module


class _Query:
    def __init__(self, rows):
        self._rows = rows
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self._rows


def _row(row_id, event_id, field_name, from_value, to_value, **overrides):
    values = {
        "id": row_id,
        "event_id": event_id,
        "field_name": field_name,
        "entity_type": "order",
        "entity_id": None,
        "entity_label": None,
        "from_value": from_value,
        "to_value": to_value,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_queries(monkeypatch, audit_rows, states=()):
    queries = {}

    def query(model):
        if model is module.OrderAuditLog:
            queries["audit"] = _Query(audit_rows)
            return queries["audit"]
        if model is module.ItemState:
            return _Query(list(states))
        raise AssertionError(f"unexpected query for {model}")

    monkeypatch.setattr(module.db.session, "query", query)
    return queries


def test_changes_are_grouped_onto_their_event(monkeypatch):
    _patch_queries(
        monkeypatch,
        [
            _row(1, "evt-a", "client_email", "a@x.io", "b@x.io"),
            _row(2, "evt-b", "help_to_carry", False, True),
            _row(3, "evt-a", "reference_number", "R1", "R2"),
        ],
    )
    events = [SimpleNamespace(event_id="evt-a"), SimpleNamespace(event_id="evt-b")]

    grouped = module._load_changes_by_event_id(10, events, SimpleNamespace(team_id=None))

    assert [change["field_name"] for change in grouped["evt-a"]] == [
        "client_email",
        "reference_number",
    ]
    assert [change["to_value"] for change in grouped["evt-b"]] == [True]


def test_team_scope_is_applied_when_present(monkeypatch):
    queries = _patch_queries(monkeypatch, [])

    module._load_changes_by_event_id(10, [SimpleNamespace(event_id="evt-a")], SimpleNamespace(team_id=7))

    assert any("team_id" in str(criterion) for criterion in queries["audit"].filters)


def test_events_without_uuid_skip_the_query(monkeypatch):
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: (_ for _ in ()).throw(AssertionError("should not query")),
    )

    assert module._load_changes_by_event_id(10, [SimpleNamespace(event_id=None)], SimpleNamespace(team_id=7)) == {}


def test_item_state_changes_get_state_names(monkeypatch):
    _patch_queries(
        monkeypatch,
        [_row(1, "evt-a", "item_state_id", 1, 2, entity_type="item", entity_id="9")],
        states=[SimpleNamespace(id=1, name="Open"), SimpleNamespace(id=2, name="Packed")],
    )

    grouped = module._load_changes_by_event_id(10, [SimpleNamespace(event_id="evt-a")], SimpleNamespace(team_id=None))

    assert (grouped["evt-a"][0]["from_label"], grouped["evt-a"][0]["to_label"]) == ("Open", "Packed")
