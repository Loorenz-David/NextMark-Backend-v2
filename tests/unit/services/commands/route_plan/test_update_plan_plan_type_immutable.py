from __future__ import annotations

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed

# route_plan.local_delivery imports back into update_plan, so importing
# update_plan first hits a pre-existing circular import. Loading the subpackage
# ahead of it resolves the order.
import Delivery_app_BK.services.commands.route_plan.local_delivery  # noqa: F401
from Delivery_app_BK.services.commands.route_plan import update_plan as module


def _ctx():
    return SimpleNamespace(
        set_relationship_map=lambda *_a, **_k: None,
        incoming_data={},
        identity={},
        team_id=1,
        user_id=None,
    )


def test_changing_plan_type_after_creation_is_rejected(monkeypatch):
    # The type decides which domain owns the plan's orders and what artifacts
    # they carry; flipping it in place would strand every assigned order.
    monkeypatch.setattr(
        module,
        "extract_targets",
        lambda _ctx: [{"target_id": 1, "fields": {"plan_type": "store_pickup"}}],
    )

    with pytest.raises(ValidationFailed) as exc:
        module.update_plan(_ctx())

    assert "plan_type cannot be changed" in str(exc.value)


def test_legacy_plan_type_fields_are_still_dropped_silently(monkeypatch):
    # These never mapped to a column; they are ignored rather than rejected so
    # older clients keep working.
    seen_fields: list[dict] = []
    monkeypatch.setattr(
        module,
        "extract_targets",
        lambda _ctx: [
            {
                "target_id": 1,
                "fields": {"label": "Renamed", "international_shipping": {"x": 1}},
            }
        ],
    )

    def _update_instance(_ctx, _model, fields, _target_id):
        seen_fields.append(fields)
        return SimpleNamespace(
            id=1, team_id=1, label="Renamed", start_date=None, end_date=None,
            updated_at=None, plan_type="local_delivery", date_strategy="single",
        )

    monkeypatch.setattr(module, "update_instance", _update_instance)
    monkeypatch.setattr(module, "touch_route_freshness", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "notify_delivery_planning_event", lambda **_k: None)
    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(session=SimpleNamespace(get=lambda *_a, **_k: None, commit=lambda: None)),
    )

    module.update_plan(_ctx())

    assert seen_fields == [{"label": "Renamed"}]
