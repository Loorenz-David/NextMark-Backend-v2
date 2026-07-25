import csv
import importlib.util
import sys
from datetime import date
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


def test_validate_future_assignments_fails_closed_for_other_plan(monkeypatch):
    target_plan = SimpleNamespace(id=20)
    target_group = SimpleNamespace(id=21, route_plan_id=20)
    conflicting_order = SimpleNamespace(id=30, route_plan_id=99, route_group_id=100)

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

    session = SimpleNamespace(query=lambda model: Query(model))
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

    with pytest.raises(ValueError, match="different route plan"):
        IMPORTER.validate_future_assignments(
            team_id=5,
            future_by_date={date(2026, 4, 1): [prepared]},
        )


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

    def fake_build(**kwargs):
        built_calls.append(kwargs)
        return SimpleNamespace(id=30)

    monkeypatch.setattr(IMPORTER, "build_and_insert_order", fake_build)

    def prepared(source_id):
        return IMPORTER.PreparedRow(
            raw={"id": source_id, "delivery_date": "2026-04-01"},
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
