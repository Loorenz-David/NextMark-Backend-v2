"""Unit tests for the zone-inference + No-Zone fallback resolver in the local-delivery objective."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.plan_objectives import local_delivery as module


class _DummyCtx:
    def __init__(self, team_id: int = 1) -> None:
        self.team_id = team_id


def _group(
    group_id: int,
    zone_id: int | None,
    *,
    is_system_default_bucket: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=group_id,
        zone_id=zone_id,
        team_id=1,
        route_plan_id=10,
        is_system_default_bucket=is_system_default_bucket,
    )


def _order(order_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(id=order_id)


def _zone_assignment(zone_id: int | None, is_unassigned: bool = False) -> SimpleNamespace:
    return SimpleNamespace(zone_id=zone_id, is_unassigned=is_unassigned, team_id=1)


# ── helpers to patch db.session.query ───────────────────────────────────────

class _RouteGroupQuery:
    def __init__(self, groups: list) -> None:
        self._groups = groups

    def filter(self, *_args, **_kwargs):
        # Simulate all() returning all stubs; fine because
        # the function applies Python-level matching on top.
        return self

    def order_by(self, *_):
        return self

    def one_or_none(self):
        return self._groups[0] if self._groups else None

    def all(self):
        return list(self._groups)


class _ZoneAssignmentQuery:
    def __init__(self, assignment) -> None:
        self._assignment = assignment

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._assignment


def _make_query(groups: list, zone_assignment=None):
    def _query(model_or_col):
        if model_or_col is module.RouteGroup:
            return _RouteGroupQuery(groups)
        if model_or_col is module.OrderZoneAssignment:
            return _ZoneAssignmentQuery(zone_assignment)
        raise AssertionError(f"Unexpected query model: {model_or_col}")

    return _query


# ── Explicit route_group_id ───────────────────────────────────────────────────

def test_explicit_route_group_id_returns_matching_group(monkeypatch):
    ctx = _DummyCtx()
    target = _group(7, zone_id=3)
    monkeypatch.setattr(module.db.session, "query", _make_query([target]))

    result = module._get_route_group(ctx, route_plan_id=10, route_group_id=7)

    assert result is target


def test_explicit_route_group_id_not_found_raises(monkeypatch):
    ctx = _DummyCtx()
    monkeypatch.setattr(module.db.session, "query", _make_query([]))

    with pytest.raises(ValidationFailed, match="Route group not found"):
        module._get_route_group(ctx, route_plan_id=10, route_group_id=99)


# ── Single-group shortcut ─────────────────────────────────────────────────────

def test_single_group_returned_without_inference(monkeypatch):
    ctx = _DummyCtx()
    only = _group(5, zone_id=2)
    monkeypatch.setattr(module.db.session, "query", _make_query([only]))

    result = module._get_route_group(ctx, route_plan_id=10, route_group_id=None)

    assert result is only


# ── Zone inference ────────────────────────────────────────────────────────────

def test_zone_inference_returns_matching_zone_group(monkeypatch):
    """Order assigned to zone 3 → picks the route group that owns zone 3."""
    ctx = _DummyCtx()
    no_zone = _group(1, zone_id=None)
    zone3 = _group(2, zone_id=3)
    zone7 = _group(3, zone_id=7)
    assignment = _zone_assignment(zone_id=3)

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([no_zone, zone3, zone7], zone_assignment=assignment),
    )

    result = module._get_route_group(
        ctx, route_plan_id=10, route_group_id=None, order_instance=_order(501)
    )

    assert result is zone3


def test_zone_inference_fallback_when_zone_group_absent(monkeypatch):
    """Order assigned to zone 99 which has no route group → falls back to No-Zone bucket."""
    ctx = _DummyCtx()
    no_zone = _group(1, zone_id=None)
    zone3 = _group(2, zone_id=3)
    assignment = _zone_assignment(zone_id=99)

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([no_zone, zone3], zone_assignment=assignment),
    )

    result = module._get_route_group(
        ctx, route_plan_id=10, route_group_id=None, order_instance=_order(501)
    )

    assert result is no_zone


def test_unassigned_order_falls_back_to_no_zone_group(monkeypatch):
    """Order is_unassigned=True → zone inference is skipped, falls back to No-Zone."""
    ctx = _DummyCtx()
    no_zone = _group(1, zone_id=None)
    zone3 = _group(2, zone_id=3)
    assignment = _zone_assignment(zone_id=3, is_unassigned=True)

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([no_zone, zone3], zone_assignment=assignment),
    )

    result = module._get_route_group(
        ctx, route_plan_id=10, route_group_id=None, order_instance=_order(501)
    )

    assert result is no_zone


def test_no_zone_assignment_falls_back_to_no_zone_group(monkeypatch):
    """Order has no zone assignment record at all → falls back to No-Zone."""
    ctx = _DummyCtx()
    no_zone = _group(1, zone_id=None)
    zone3 = _group(2, zone_id=3)

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([no_zone, zone3], zone_assignment=None),
    )

    result = module._get_route_group(
        ctx, route_plan_id=10, route_group_id=None, order_instance=_order(501)
    )

    assert result is no_zone


def test_order_without_id_falls_back_to_no_zone_group(monkeypatch):
    """Order without a persisted id → inference is skipped, falls back to No-Zone."""
    ctx = _DummyCtx()
    no_zone = _group(1, zone_id=None)
    zone3 = _group(2, zone_id=3)

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([no_zone, zone3], zone_assignment=None),
    )

    result = module._get_route_group(
        ctx, route_plan_id=10, route_group_id=None, order_instance=_order(None)
    )

    assert result is no_zone


def test_fallback_prefers_system_default_no_zone_group(monkeypatch):
    ctx = _DummyCtx()
    manual_no_zone = _group(1, zone_id=None, is_system_default_bucket=False)
    default_no_zone = _group(2, zone_id=None, is_system_default_bucket=True)
    zone3 = _group(3, zone_id=3)

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([manual_no_zone, default_no_zone, zone3], zone_assignment=None),
    )

    result = module._get_route_group(
        ctx, route_plan_id=10, route_group_id=None, order_instance=_order(501)
    )

    assert result is default_no_zone


# ── Failure paths ─────────────────────────────────────────────────────────────

def test_no_groups_at_all_raises(monkeypatch):
    ctx = _DummyCtx()
    monkeypatch.setattr(module.db.session, "query", _make_query([]))

    with pytest.raises(ValidationFailed, match="Route group not found"):
        module._get_route_group(ctx, route_plan_id=10, route_group_id=None)


def test_no_zone_group_and_no_match_raises(monkeypatch):
    """Multiple zone-specific groups exist but no No-Zone bucket and no matching zone."""
    ctx = _DummyCtx()
    zone3 = _group(2, zone_id=3)
    zone7 = _group(3, zone_id=7)
    assignment = _zone_assignment(zone_id=99)  # no match

    monkeypatch.setattr(
        module.db.session, "query",
        _make_query([zone3, zone7], zone_assignment=assignment),
    )

    with pytest.raises(ValidationFailed, match="Cannot determine destination route group"):
        module._get_route_group(
            ctx, route_plan_id=10, route_group_id=None, order_instance=_order(501)
        )
