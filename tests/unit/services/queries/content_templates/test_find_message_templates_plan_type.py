from importlib import import_module
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import MultiDict

from Delivery_app_BK.services.context import ServiceContext

# The package __init__ re-exports the functions under the module names, so the
# modules themselves have to be imported by path.
module = import_module("Delivery_app_BK.services.queries.content_templates.messages.find_message_templates")
serializer = import_module("Delivery_app_BK.services.queries.content_templates.messages.serialize_message_templates")


class _FakeQuery:
    def __init__(self):
        self.clauses: list = []

    def filter(self, *clauses):
        self.clauses.extend(clauses)
        return self

    def order_by(self, *_args):
        return self


def _run(monkeypatch, params, *, query_params=None):
    fake = _FakeQuery()
    monkeypatch.setattr(module, "apply_pagination_by_id", lambda query, **_kwargs: query)
    ctx = ServiceContext(query_params=query_params if query_params is not None else params)
    ctx.inject_team_id = False
    module.find_message_templates(params, ctx, query=fake)
    return fake.clauses


def _plan_type_values(clauses) -> list[str] | None:
    """The bound value list of the `plan_type IN (...)` clause, if one was added."""
    clause = next((c for c in clauses if "message_template.plan_type" in str(c)), None)
    if clause is None:
        return None
    return list(clause.right.value)


def test_scalar_plan_type_filters_with_in(monkeypatch):
    clauses = _run(monkeypatch, {"plan_type": "store_pickup"})

    assert _plan_type_values(clauses) == ["store_pickup"]


def test_comma_separated_plan_types_are_split(monkeypatch):
    clauses = _run(monkeypatch, {"plan_type": "store_pickup,local_delivery"})

    assert _plan_type_values(clauses) == ["store_pickup", "local_delivery"]


def test_bracketed_list_from_multidict_is_read_via_getlist(monkeypatch):
    query_params = MultiDict([("plan_type[]", "store_pickup"), ("plan_type[]", "international_shipping")])
    clauses = _run(monkeypatch, {}, query_params=query_params)

    assert _plan_type_values(clauses) == ["store_pickup", "international_shipping"]


def test_no_plan_type_means_no_plan_type_filter(monkeypatch):
    clauses = _run(monkeypatch, {"channel": "sms"})

    assert _plan_type_values(clauses) is None


def test_blank_plan_type_values_match_nothing(monkeypatch):
    clauses = _run(monkeypatch, {"plan_type": ["", "  "]})

    assert _plan_type_values(clauses) is None
    assert any(str(clause).lower() == "false" for clause in clauses)


@pytest.mark.parametrize(
    "serialize",
    [serializer.serialize_message_templates, serializer.serialize_message_templates_bootstrap],
)
def test_serializers_expose_plan_type(monkeypatch, serialize):
    monkeypatch.setattr(serializer, "map_return_values", lambda unpacked, ctx, key: unpacked)
    instance = SimpleNamespace(
        id=1,
        client_id="message_template_1",
        event="order_ready",
        enable=True,
        subject=None,
        template=[],
        ask_permission=False,
        name="Ready",
        channel="sms",
        plan_type="store_pickup",
        schedule_offset_value=None,
        schedule_offset_unit=None,
    )

    [serialized] = serialize([instance], ServiceContext())

    assert serialized["plan_type"] == "store_pickup"
