import csv
import importlib.util
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


IMPORTER_PATH = Path(__file__).parents[2] / "beyo-data-transfer" / "importer.py"
SPEC = importlib.util.spec_from_file_location("beyo_data_transfer_importer", IMPORTER_PATH)
IMPORTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = IMPORTER
SPEC.loader.exec_module(IMPORTER)


def _csv_row(source_id: str, delivery_date: str, items: str = "[]") -> dict[str, str]:
    return {
        "id": source_id,
        "delivery_date": delivery_date,
        "items": items,
        "address": "Main Street 1, 111 11 Stockholm, Sweden",
        "coordinates": '{"lat": 59.3, "lng": 18.0}',
        "order_state": "Active",
    }


def test_load_and_group_csv_groups_future_rows_by_delivery_date(tmp_path, monkeypatch):
    csv_path = tmp_path / "orders.csv"
    rows = [
        _csv_row("1", "2026-03-31"),
        _csv_row("2", "2026-04-01", "NULL"),
        _csv_row("3", "2026-04-01"),
        _csv_row("4", "2026-03-30"),
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.setattr(IMPORTER, "CSV_PATH", csv_path)
    groups = IMPORTER.load_and_group_csv(date(2026, 3, 31))

    assert [row.raw["id"] for row in groups["past"][date(2026, 3, 30)]] == ["4"]
    assert [row.raw["id"] for row in groups["future_by_date"][date(2026, 3, 31)]] == ["1"]
    assert [row.raw["id"] for row in groups["future_by_date"][date(2026, 4, 1)]] == ["2", "3"]


def test_load_and_group_csv_rejects_duplicate_source_ids(tmp_path, monkeypatch):
    csv_path = tmp_path / "orders.csv"
    rows = [_csv_row("1", "2026-03-31"), _csv_row("1", "2026-04-01")]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.setattr(IMPORTER, "CSV_PATH", csv_path)
    with pytest.raises(ValueError, match="duplicate source id"):
        IMPORTER.load_and_group_csv(date(2026, 3, 31))


def test_ensure_future_plan_bundle_is_open_unoptimized_and_has_no_actuals(monkeypatch):
    class Query:
        def __init__(self, result):
            self.result = result

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self.result

        def all(self):
            return []

    class Session:
        def __init__(self):
            self.objects = []

        def query(self, model):
            return Query(None)

        def add(self, instance):
            self.objects.append(instance)
            if isinstance(instance, IMPORTER.RoutePlan):
                instance.id = 11
            elif isinstance(instance, IMPORTER.RouteGroup):
                instance.id = 12
            elif isinstance(instance, IMPORTER.RouteSolution):
                instance.id = 13

        def flush(self):
            return None

        def get(self, model, _id):
            if model is IMPORTER.Facility:
                return SimpleNamespace(
                    id=7,
                    team_id=5,
                    property_location={
                        "street_address": "Warehouse 1",
                        "country": "Sweden",
                        "coordinates": {"lat": 59.3, "lng": 18.0},
                    },
                )
            return None

    session = Session()
    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=session))

    plan, group, solution = IMPORTER.ensure_future_plan_bundle(
        team_id=5,
        driver_id=9,
        identity={"time_zone": "Europe/Stockholm"},
        delivery_date=date(2026, 4, 1),
        facility_id=7,
        vehicle_id=8,
    )

    assert plan.state_id == IMPORTER.PlanStateId.OPEN
    assert group.state_id == IMPORTER.PlanStateId.OPEN
    assert group.route_plan_id == plan.id
    assert solution.route_group_id == group.id
    assert solution.is_selected is True
    assert solution.is_optimized == IMPORTER.IS_OPTIMIZED_NOT_OPTIMIZED
    assert solution.actual_start_time is None
    assert solution.actual_end_time is None
    assert solution.total_distance_meters is None
    assert solution.total_travel_time_seconds is None


def test_ensure_future_plan_bundle_reuses_legacy_same_date_plan(monkeypatch):
    legacy_plan = SimpleNamespace(
        id=41,
        team_id=5,
        label="Import 2026-04-01",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

        def all(self):
            return [legacy_plan] if self.model is IMPORTER.RoutePlan else []

    class Session:
        def __init__(self):
            self.objects = []

        def query(self, model):
            return Query(model)

        def add(self, instance):
            self.objects.append(instance)
            if isinstance(instance, IMPORTER.RouteGroup):
                instance.id = 42
            elif isinstance(instance, IMPORTER.RouteSolution):
                instance.id = 43

        def flush(self):
            return None

        def get(self, model, _id):
            if model is IMPORTER.Facility:
                return SimpleNamespace(
                    id=7,
                    team_id=5,
                    property_location={
                        "street_address": "Warehouse 1",
                        "country": "Sweden",
                        "coordinates": {"lat": 59.3, "lng": 18.0},
                    },
                )
            return None

    session = Session()
    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=session))

    plan, group, _solution = IMPORTER.ensure_future_plan_bundle(
        team_id=5,
        driver_id=9,
        identity={"time_zone": "Europe/Stockholm"},
        delivery_date=date(2026, 4, 1),
        facility_id=7,
        vehicle_id=8,
    )

    assert plan is legacy_plan
    assert group.route_plan_id == legacy_plan.id
    assert not any(isinstance(obj, IMPORTER.RoutePlan) for obj in session.objects)


def test_validate_future_assignments_fails_closed_for_other_plan(monkeypatch):
    target_plan = SimpleNamespace(id=20)
    target_group = SimpleNamespace(id=21, route_plan_id=20)
    conflicting_order = SimpleNamespace(id=30, route_plan_id=99, route_group_id=100)
    conflicting_plan = SimpleNamespace(
        id=99,
        team_id=5,
        label="Import 2026-04-02",
        start_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
    )

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            if self.model is IMPORTER.RoutePlan:
                return target_plan
            if self.model is IMPORTER.RouteGroup:
                return target_group
            return conflicting_order

        def all(self):
            return []

    session = SimpleNamespace(
        query=lambda model: Query(model),
        get=lambda model, value: conflicting_plan if value == 99 else None,
    )
    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=session))
    prepared = IMPORTER.PreparedRow(
        raw={"id": "30"},
        delivery_date=date(2026, 4, 1),
        parsed_items=[],
        total_weight=0,
        total_volume=0,
        total_items=0,
        item_type_counts=None,
    )

    with pytest.raises(ValueError, match="does not match"):
        IMPORTER.validate_future_assignments(
            team_id=5,
            future_by_date={date(2026, 4, 1): [prepared]},
        )


def test_validate_future_assignments_allows_existing_same_date_plan(monkeypatch):
    existing_plan = SimpleNamespace(
        id=99,
        team_id=5,
        label="Legacy delivery plan 2026-04-01",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    existing_group = SimpleNamespace(id=100, team_id=5, route_plan_id=99)
    existing_order = SimpleNamespace(id=30, route_plan_id=99, route_group_id=100)
    prepared = IMPORTER.PreparedRow(
        raw={"id": "30"},
        delivery_date=date(2026, 4, 1),
        parsed_items=[],
        total_weight=0,
        total_volume=0,
        total_items=0,
        item_type_counts=None,
    )

    monkeypatch.setattr(
        IMPORTER,
        "find_existing_import_order",
        lambda _team_id, _source_id: existing_order,
    )

    class Session:
        def query(self, model):
            class Query:
                def filter(self, *_args, **_kwargs):
                    return self

                def all(self):
                    return [existing_plan] if model is IMPORTER.RoutePlan else []

            return Query()

        def get(self, model, value):
            if model is IMPORTER.RoutePlan and value == 99:
                return existing_plan
            if model is IMPORTER.RouteGroup and value == 100:
                return existing_group
            return None

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))

    IMPORTER.validate_future_assignments(
        team_id=5,
        future_by_date={date(2026, 4, 1): [prepared]},
    )


def test_validate_future_assignments_uses_explicit_canonical_plan_for_split_orders(monkeypatch):
    old_plan = SimpleNamespace(
        id=41,
        team_id=5,
        label="Legacy plan 2026-07-26",
        start_date=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    canonical_plan = SimpleNamespace(
        id=42,
        team_id=5,
        label="Plan for July 26",
        # Legacy plan metadata can contain the wrong UTC date; the canonical
        # operator label is the explicit migration authority.
        start_date=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    old_group = SimpleNamespace(id=51, team_id=5, route_plan_id=41)
    canonical_group = SimpleNamespace(id=52, team_id=5, route_plan_id=42)
    orders = {
        "1": SimpleNamespace(id=301, route_plan_id=41, route_group_id=51),
        "2": SimpleNamespace(id=302, route_plan_id=42, route_group_id=52),
    }
    monkeypatch.setattr(
        IMPORTER,
        "find_existing_import_order",
        lambda _team_id, source_id: orders.get(source_id),
    )

    class Session:
        def query(self, model):
            class Query:
                def filter(self, *_args, **_kwargs):
                    return self

                def all(self):
                    return [old_plan, canonical_plan] if model is IMPORTER.RoutePlan else []

            return Query()

        def get(self, model, value):
            values = {
                (IMPORTER.RoutePlan, 41): old_plan,
                (IMPORTER.RoutePlan, 42): canonical_plan,
                (IMPORTER.RouteGroup, 51): old_group,
                (IMPORTER.RouteGroup, 52): canonical_group,
            }
            return values.get((model, value))

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))

    rows = [
        IMPORTER.PreparedRow(
            raw={"id": source_id},
            delivery_date=date(2026, 7, 26),
            parsed_items=[],
            total_weight=0,
            total_volume=0,
            total_items=0,
            item_type_counts=None,
        )
        for source_id in ("1", "2")
    ]

    IMPORTER.validate_future_assignments(
        team_id=5,
        future_by_date={date(2026, 7, 26): rows},
    )


def test_future_import_reassigns_same_date_orders_to_explicit_canonical_plan(monkeypatch):
    old_order = SimpleNamespace(
        id=301,
        route_plan_id=41,
        route_group_id=51,
        client_id=IMPORTER.make_entity_client_id("order", "1"),
    )
    canonical_order = SimpleNamespace(
        id=302,
        route_plan_id=42,
        route_group_id=52,
        client_id=IMPORTER.make_entity_client_id("order", "2"),
    )
    orders = {"1": old_order, "2": canonical_order}
    canonical_plan = SimpleNamespace(
        id=42,
        team_id=5,
        label="Plan for July 26",
        total_orders=2,
    )
    canonical_group = SimpleNamespace(id=52)
    solution = SimpleNamespace(id=53)
    refreshed = []

    monkeypatch.setattr(
        IMPORTER,
        "find_existing_import_order",
        lambda _team_id, source_id: orders.get(source_id),
    )
    monkeypatch.setattr(
        IMPORTER,
        "ensure_future_plan_bundle",
        lambda **_kwargs: (canonical_plan, canonical_group, solution),
    )
    monkeypatch.setattr(IMPORTER, "reconcile_existing_order", lambda **_kwargs: 0)
    monkeypatch.setattr(
        IMPORTER,
        "refresh_import_plan_totals",
        lambda plan, group: refreshed.append((plan, group)),
    )

    old_plan = SimpleNamespace(
        id=41,
        team_id=5,
        label="Legacy plan 2026-07-26",
        start_date=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    old_group = SimpleNamespace(id=51, team_id=5, route_plan_id=41)

    class Session:
        def flush(self):
            return None

        def get(self, model, value):
            if model is IMPORTER.RoutePlan and value == 41:
                return old_plan
            if model is IMPORTER.RouteGroup and value == 51:
                return old_group
            return None

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))

    def prepared(source_id):
        return IMPORTER.PreparedRow(
            raw={"id": source_id, "delivery_date": "2026-07-26"},
            delivery_date=date(2026, 7, 26),
            parsed_items=[],
            total_weight=0,
            total_volume=0,
            total_items=0,
            item_type_counts=None,
        )

    IMPORTER.import_future_orders(
        team_id=5,
        driver_id=9,
        identity={"time_zone": "Europe/Stockholm"},
        as_of_date=date(2026, 7, 25),
        future_by_date={date(2026, 7, 26): [prepared("1"), prepared("2")]},
        facility_id=7,
        vehicle_id=8,
    )

    assert (old_order.route_plan_id, old_order.route_group_id) == (42, 52)
    assert (canonical_order.route_plan_id, canonical_order.route_group_id) == (42, 52)
    assert (old_plan, old_group) in refreshed


def test_cross_date_canonical_reassignment_requires_explicit_flag(monkeypatch):
    old_plan = SimpleNamespace(
        id=41,
        team_id=5,
        label="Import 2026-08-16",
        start_date=datetime(2026, 8, 16, tzinfo=timezone.utc),
    )
    canonical_plan = SimpleNamespace(
        id=42,
        team_id=5,
        label="Plan for July 26",
        start_date=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    canonical_group = SimpleNamespace(id=52, team_id=5, route_plan_id=42)
    existing_order = SimpleNamespace(id=301, route_plan_id=41, route_group_id=51)
    monkeypatch.setattr(
        IMPORTER,
        "find_existing_import_order",
        lambda _team_id, _source_id: existing_order,
    )

    class Session:
        def query(self, model):
            class Query:
                def filter(self, *_args, **_kwargs):
                    return self

                def first(self):
                    return canonical_group if model is IMPORTER.RouteGroup else None

                def all(self):
                    if model is IMPORTER.RoutePlan:
                        return [old_plan, canonical_plan]
                    return []

            return Query()

        def get(self, model, value):
            values = {
                (IMPORTER.RoutePlan, 41): old_plan,
                (IMPORTER.RoutePlan, 42): canonical_plan,
                (IMPORTER.RouteGroup, 52): canonical_group,
            }
            return values.get((model, value))

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))
    prepared = IMPORTER.PreparedRow(
        raw={"id": "1"},
        delivery_date=date(2026, 7, 26),
        parsed_items=[],
        total_weight=0,
        total_volume=0,
        total_items=0,
        item_type_counts=None,
    )

    with pytest.raises(ValueError, match="allow-canonical-reassignment"):
        IMPORTER.validate_future_assignments(
            team_id=5,
            future_by_date={date(2026, 7, 26): [prepared]},
        )

    IMPORTER.validate_future_assignments(
        team_id=5,
        allow_canonical_reassignment=True,
        future_by_date={date(2026, 7, 26): [prepared]},
    )


def test_cross_date_reassignment_allows_planning_only_optimized_stop(monkeypatch):
    old_plan = SimpleNamespace(
        id=209,
        team_id=5,
        label="Import 2026-08-16",
        start_date=datetime(2026, 8, 16, tzinfo=timezone.utc),
    )
    canonical_plan = SimpleNamespace(
        id=210,
        team_id=5,
        label="Plan for July 26",
        start_date=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    old_group = SimpleNamespace(id=219, team_id=5, route_plan_id=209)
    old_solution = SimpleNamespace(
        id=209,
        team_id=5,
        route_group_id=219,
        is_optimized="optimize",
        actual_start_time=None,
        actual_end_time=None,
        actual_end_time_source=None,
    )
    planning_stop = SimpleNamespace(
        id=1324,
        route_solution_id=209,
        expected_arrival_time=datetime(2026, 8, 16, 15, 52, 17, tzinfo=timezone.utc),
        actual_arrival_time=None,
        actual_departure_time=None,
        reason_was_skipped=None,
    )
    order = SimpleNamespace(id=1296, route_plan_id=209, route_group_id=219)

    class Session:
        def query(self, model):
            class Query:
                def filter(self, *_args, **_kwargs):
                    return self

                def all(self):
                    return [planning_stop] if model is IMPORTER.RouteSolutionStop else []

            return Query()

        def get(self, model, value):
            values = {
                (IMPORTER.RoutePlan, 209): old_plan,
                (IMPORTER.RouteSolution, 209): old_solution,
                (IMPORTER.RouteGroup, 219): old_group,
            }
            return values.get((model, value))

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))

    stops = IMPORTER._validate_canonical_reassignment(
        order=order,
        target_plan=canonical_plan,
        delivery_date=date(2026, 7, 26),
        time_zone="Europe/Stockholm",
        allow_cross_date=True,
    )

    assert stops == [planning_stop]


def test_cross_date_reassignment_rejects_execution_data(monkeypatch):
    old_plan = SimpleNamespace(
        id=209,
        team_id=5,
        label="Import 2026-08-16",
        start_date=datetime(2026, 8, 16, tzinfo=timezone.utc),
    )
    canonical_plan = SimpleNamespace(
        id=210,
        team_id=5,
        label="Plan for July 26",
    )
    old_group = SimpleNamespace(id=219, team_id=5, route_plan_id=209)
    old_solution = SimpleNamespace(
        id=209,
        team_id=5,
        route_group_id=219,
        actual_start_time=None,
        actual_end_time=None,
        actual_end_time_source=None,
    )
    executed_stop = SimpleNamespace(
        id=1324,
        route_solution_id=209,
        actual_arrival_time=datetime(2026, 8, 16, 15, 52, 17, tzinfo=timezone.utc),
        actual_departure_time=None,
        reason_was_skipped=None,
    )
    order = SimpleNamespace(id=1296, route_plan_id=209, route_group_id=219)

    class Session:
        def query(self, _model):
            class Query:
                def filter(self, *_args, **_kwargs):
                    return self

                def all(self):
                    return [executed_stop]

            return Query()

        def get(self, model, value):
            values = {
                (IMPORTER.RoutePlan, 209): old_plan,
                (IMPORTER.RouteSolution, 209): old_solution,
                (IMPORTER.RouteGroup, 219): old_group,
            }
            return values.get((model, value))

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))

    with pytest.raises(ValueError, match="execution data"):
        IMPORTER._validate_canonical_reassignment(
            order=order,
            target_plan=canonical_plan,
            delivery_date=date(2026, 7, 26),
            time_zone="Europe/Stockholm",
            allow_cross_date=True,
        )


def test_future_import_removes_validated_planning_stop_before_reassignment(monkeypatch):
    old_plan = SimpleNamespace(id=209, team_id=5)
    old_group = SimpleNamespace(id=219, team_id=5, route_plan_id=209)
    canonical_plan = SimpleNamespace(
        id=210,
        team_id=5,
        label="Plan for July 26",
        total_orders=1,
    )
    canonical_group = SimpleNamespace(id=220)
    canonical_solution = SimpleNamespace(id=211)
    existing_order = SimpleNamespace(
        id=1296,
        client_id=IMPORTER.make_entity_client_id("order", "1296"),
        route_plan_id=209,
        route_group_id=219,
    )
    old_solution = SimpleNamespace(
        id=309,
        is_optimized="optimize",
        algorithm="test",
        score=100,
        total_distance_meters=5000,
        total_travel_time_seconds=900,
        start_leg_polyline={"encoded": "start"},
        end_leg_polyline={"encoded": "end"},
        has_route_warnings=True,
        route_warnings=["warning"],
    )
    planning_stop = SimpleNamespace(id=1324, route_solution_id=309)
    remaining_stop = SimpleNamespace(
        id=1325,
        route_solution_id=309,
        eta_status="valid",
        to_next_polyline={"encoded": "next"},
    )

    class Session:
        def __init__(self):
            self.deleted = []

        def query(self, _model):
            class Query:
                def filter(self, *_args, **_kwargs):
                    return self

                def all(self):
                    return [planning_stop, remaining_stop]

            return Query()

        def delete(self, value):
            self.deleted.append(value)

        def flush(self):
            return None

        def get(self, model, value):
            if model is IMPORTER.RoutePlan and value == 209:
                return old_plan
            if model is IMPORTER.RouteGroup and value == 219:
                return old_group
            if model is IMPORTER.RouteSolution and value == 309:
                return old_solution
            return None

    session = Session()
    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(
        IMPORTER,
        "find_existing_import_order",
        lambda _team_id, _source_id: existing_order,
    )
    monkeypatch.setattr(
        IMPORTER,
        "ensure_future_plan_bundle",
        lambda **_kwargs: (canonical_plan, canonical_group, canonical_solution),
    )
    monkeypatch.setattr(IMPORTER, "reconcile_existing_order", lambda **_kwargs: 0)
    monkeypatch.setattr(IMPORTER, "refresh_import_plan_totals", lambda *_args: None)
    monkeypatch.setattr(
        IMPORTER,
        "_validate_canonical_reassignment",
        lambda **_kwargs: [planning_stop],
    )
    prepared = IMPORTER.PreparedRow(
        raw={"id": "1296", "delivery_date": "2026-07-26"},
        delivery_date=date(2026, 7, 26),
        parsed_items=[],
        total_weight=0,
        total_volume=0,
        total_items=0,
        item_type_counts=None,
    )

    IMPORTER.import_future_orders(
        team_id=5,
        driver_id=9,
        identity={"time_zone": "Europe/Stockholm"},
        as_of_date=date(2026, 7, 26),
        future_by_date={date(2026, 7, 26): [prepared]},
        facility_id=7,
        vehicle_id=8,
        allow_canonical_reassignment=True,
    )

    assert session.deleted == [planning_stop]
    assert (existing_order.route_plan_id, existing_order.route_group_id) == (210, 220)
    assert old_solution.is_optimized == IMPORTER.IS_OPTIMIZED_NOT_OPTIMIZED
    assert old_solution.total_distance_meters is None
    assert old_solution.total_travel_time_seconds is None
    assert remaining_stop.eta_status == "stale"
    assert remaining_stop.to_next_polyline is None


def test_reconcile_existing_order_backfills_missing_csv_fields_and_items(monkeypatch):
    customer = SimpleNamespace(first_name=None, last_name=None, email=None)
    existing_order = SimpleNamespace(
        id=30,
        client_id="legacy-client-id",
        costumer=None,
        costumer_id=None,
        client_first_name=None,
        client_last_name=None,
        client_email=None,
        client_primary_phone=None,
        client_address=None,
        operation_type=None,
        help_to_carry=None,
        order_state_id=None,
        order_plan_objective=None,
        creation_date=None,
        order_notes=None,
        total_weight_g=None,
        total_volume_cm3=None,
        total_item_count=None,
        item_type_counts=None,
    )
    parsed_item = IMPORTER.ParsedItem(
        article_number="CHAIR-1",
        item_type="Dining Chair",
        quantity=2,
        weight=5000,
        dimension_height=100,
        dimension_width=55,
        dimension_depth=55,
        properties=None,
    )
    raw = _csv_row("30", "2026-04-01")
    raw.update(
        {
            "name": "Alice",
            "after_name": "Andersson",
            "email": "alice@example.test",
            "phone": "+46701234567",
            "order_type": "delivery",
            "help_to_carry": "yes",
        }
    )
    prepared = IMPORTER.PreparedRow(
        raw=raw,
        delivery_date=date(2026, 4, 1),
        parsed_items=[parsed_item],
        total_weight=10_000,
        total_volume=302_500,
        total_items=2,
        item_type_counts={"Dining Chair": 2},
    )

    class ItemQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class Session:
        def __init__(self):
            self.added = []

        def query(self, _model):
            return ItemQuery()

        def get(self, _model, _value):
            return None

        def add(self, instance):
            self.added.append(instance)

        def flush(self):
            return None

    session = Session()
    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(IMPORTER, "resolve_or_create_costumer", lambda *_args: customer)

    changed = IMPORTER.reconcile_existing_order(
        team_id=5,
        order=existing_order,
        prepared=prepared,
        as_of_date=date(2026, 3, 31),
    )

    assert changed > 0
    assert existing_order.client_id == IMPORTER.make_entity_client_id("order", "30")
    assert existing_order.client_first_name == "Alice"
    assert existing_order.total_item_count == 2
    assert existing_order.costumer is customer
    assert len(session.added) == 1
    assert session.added[0].order_id == existing_order.id
    assert session.added[0].quantity == 2


def test_future_import_attaches_existing_order_and_creates_plan_linked_new_order(monkeypatch):
    existing = SimpleNamespace(
        client_id=IMPORTER.make_entity_client_id("order", "1"),
        route_plan_id=None,
        route_group_id=None,
    )
    plan = SimpleNamespace(id=20, total_orders=2)
    group = SimpleNamespace(id=21)
    solution = SimpleNamespace(id=22)
    built_calls = []

    class Query:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [existing]

    class Session:
        def query(self, _model):
            return Query()

        def flush(self):
            return None

    monkeypatch.setattr(IMPORTER, "db", SimpleNamespace(session=Session()))
    monkeypatch.setattr(
        IMPORTER,
        "ensure_future_plan_bundle",
        lambda **_kwargs: (plan, group, solution),
    )
    monkeypatch.setattr(
        IMPORTER,
        "reserve_order_scalar_ids",
        lambda _ctx, count: list(range(100, 100 + count)),
    )
    monkeypatch.setattr(IMPORTER, "refresh_import_plan_totals", lambda *_args: None)
    monkeypatch.setattr(
        IMPORTER,
        "find_existing_import_order",
        lambda _team_id, source_id: existing if source_id == "1" else None,
    )
    monkeypatch.setattr(IMPORTER, "reconcile_existing_order", lambda **_kwargs: 0)

    def fake_build(**kwargs):
        built_calls.append(kwargs)
        return SimpleNamespace(id=30)

    monkeypatch.setattr(IMPORTER, "build_and_insert_order", fake_build)

    def prepared(source_id):
        return IMPORTER.PreparedRow(
            raw={
                "id": source_id,
                "delivery_date": "2026-04-01",
                "address": "Main Street 1, 111 11 Stockholm, Sweden",
                "coordinates": '{"lat": 59.3, "lng": 18.0}',
                "order_state": "Active",
            },
            delivery_date=date(2026, 4, 1),
            parsed_items=[],
            total_weight=0,
            total_volume=0,
            total_items=0,
            item_type_counts=None,
        )

    IMPORTER.import_future_orders(
        team_id=5,
        driver_id=9,
        identity={"time_zone": "Europe/Stockholm"},
        as_of_date=date(2026, 3, 31),
        future_by_date={date(2026, 4, 1): [prepared("1"), prepared("2")]},
        facility_id=7,
        vehicle_id=8,
    )

    assert existing.route_plan_id == plan.id
    assert existing.route_group_id == group.id
    assert len(built_calls) == 1
    assert built_calls[0]["route_plan_id"] == plan.id
    assert built_calls[0]["route_group_id"] == group.id


def test_run_import_dry_run_does_not_create_resources(monkeypatch):
    team = SimpleNamespace(id=5, name="Test", default_country_code="SE")
    monkeypatch.setattr(
        IMPORTER,
        "resolve_target_context",
        lambda _team_id, _driver_id: (team, SimpleNamespace(id=9), "Europe/Stockholm", date(2026, 3, 31)),
    )
    monkeypatch.setattr(IMPORTER, "build_identity", lambda *_args, **_kwargs: {"time_zone": "Europe/Stockholm"})
    monkeypatch.setattr(IMPORTER, "load_and_group_csv", lambda _date: {"past": {}, "future_by_date": {}})
    monkeypatch.setattr(IMPORTER, "validate_future_assignments", lambda **_kwargs: None)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("dry run attempted a write")

    monkeypatch.setattr(IMPORTER, "create_facility", fail_if_called)
    IMPORTER.run_import(5, 9, apply=False)


def test_describe_database_target_does_not_expose_password():
    description = IMPORTER.describe_database_target(
        "postgresql://secret:password@example.test:5432/DeliveryApp"
    )

    assert description == "postgresql://example.test:5432/DeliveryApp"
    assert "password" not in description
