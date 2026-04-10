from types import SimpleNamespace

from Delivery_app_BK.services.domain.route_operations.plan import recompute_route_group_totals as module


class _RouteGroupQuery:
    def __init__(self, route_groups):
        self._route_groups = route_groups

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._route_groups)


class _RowsQuery:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)


class _ScalarQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return self._value


def _is_item_type_counts(arg) -> bool:
    return getattr(arg, "key", None) == "item_type_counts"


# ---------------------------------------------------------------------------
# Zone-backed groups
# ---------------------------------------------------------------------------

def test_recompute_route_group_totals_updates_zone_counts(monkeypatch):
    rg_zone_3 = SimpleNamespace(zone_id=3, total_orders=None, item_type_counts=None)
    rg_zone_7 = SimpleNamespace(zone_id=7, total_orders=None, item_type_counts=None)

    def _query(*args):
        first = args[0]
        if first is module.RouteGroup:
            return _RouteGroupQuery([rg_zone_3, rg_zone_7])
        if len(args) > 1 and _is_item_type_counts(args[1]):
            return _RowsQuery([(3, {"Lamp": 2})])
        return _RowsQuery([(3, 5)])

    monkeypatch.setattr(module.db.session, "query", _query)

    plan = SimpleNamespace(id=42, team_id=1)
    module.recompute_route_group_totals(plan)

    assert rg_zone_3.total_orders == 5
    assert rg_zone_7.total_orders == 0
    assert rg_zone_3.item_type_counts == {"Lamp": 2}
    assert rg_zone_7.item_type_counts is None


def test_recompute_route_group_totals_is_idempotent(monkeypatch):
    rg = SimpleNamespace(zone_id=3, total_orders=None, item_type_counts=None)

    def _query(*args):
        first = args[0]
        if first is module.RouteGroup:
            return _RouteGroupQuery([rg])
        if len(args) > 1 and _is_item_type_counts(args[1]):
            return _RowsQuery([(3, {"Sofa": 1})])
        return _RowsQuery([(3, 9)])

    monkeypatch.setattr(module.db.session, "query", _query)

    plan = SimpleNamespace(id=42, team_id=1)
    module.recompute_route_group_totals(plan)
    module.recompute_route_group_totals(plan)

    assert rg.total_orders == 9
    assert rg.item_type_counts == {"Sofa": 1}


def test_recompute_route_group_totals_skips_when_no_groups(monkeypatch):
    called = []

    def _query(*args):
        if args[0] is module.RouteGroup:
            return _RouteGroupQuery([])
        called.append(args)
        raise AssertionError("Aggregate query should not run when no groups exist")

    monkeypatch.setattr(module.db.session, "query", _query)
    module.recompute_route_group_totals(SimpleNamespace(id=42, team_id=1))

    assert called == []


# ---------------------------------------------------------------------------
# No-Zone bucket
# ---------------------------------------------------------------------------

def test_recompute_sets_no_zone_total_via_direct_order_count(monkeypatch):
    """No-Zone group total must be counted via Order.route_group_id, not zone join."""
    rg_no_zone = SimpleNamespace(zone_id=None, id=88, total_orders=None, item_type_counts=None)

    def _query(*args):
        first = args[0]
        if first is module.RouteGroup:
            return _RouteGroupQuery([rg_no_zone])
        if _is_item_type_counts(first):
            return _RowsQuery([({"Sofa": 1},), ({"Lamp": 2},)])
        return _ScalarQuery(4)

    monkeypatch.setattr(module.db.session, "query", _query)

    module.recompute_route_group_totals(SimpleNamespace(id=42, team_id=1))

    assert rg_no_zone.total_orders == 4
    assert rg_no_zone.item_type_counts == {"Sofa": 1, "Lamp": 2}


def test_no_zone_group_item_type_counts(monkeypatch):
    """No-zone bucket aggregates item_type_counts from orders by route_group_id."""
    rg_no_zone = SimpleNamespace(zone_id=None, id=33, total_orders=None, item_type_counts=None)

    def _query(*args):
        first = args[0]
        if first is module.RouteGroup:
            return _RouteGroupQuery([rg_no_zone])
        if _is_item_type_counts(first):
            return _RowsQuery([({"Sofa": 1},), ({"Sofa": 1, "Lamp": 2},)])
        return _ScalarQuery(2)

    monkeypatch.setattr(module.db.session, "query", _query)

    module.recompute_route_group_totals(SimpleNamespace(id=42, team_id=1))

    assert rg_no_zone.total_orders == 2
    assert rg_no_zone.item_type_counts == {"Sofa": 2, "Lamp": 2}


def test_recompute_mixed_zone_and_no_zone_groups(monkeypatch):
    """Plan with both zone groups and a No-Zone bucket updates both correctly."""
    rg_zone = SimpleNamespace(zone_id=3, total_orders=None, item_type_counts=None)
    rg_no_zone = SimpleNamespace(zone_id=None, id=99, total_orders=None, item_type_counts=None)

    def _query(*args):
        first = args[0]
        if first is module.RouteGroup:
            return _RouteGroupQuery([rg_zone, rg_no_zone])
        if len(args) > 1 and _is_item_type_counts(args[1]):
            return _RowsQuery([(3, {"Lamp": 5})])
        if len(args) > 1:
            return _RowsQuery([(3, 5)])
        if _is_item_type_counts(first):
            return _RowsQuery([({"Sofa": 3},)])
        return _ScalarQuery(7)

    monkeypatch.setattr(module.db.session, "query", _query)

    module.recompute_route_group_totals(SimpleNamespace(id=42, team_id=1))

    assert rg_zone.total_orders == 5
    assert rg_zone.item_type_counts == {"Lamp": 5}
    assert rg_no_zone.total_orders == 7
    assert rg_no_zone.item_type_counts == {"Sofa": 3}

