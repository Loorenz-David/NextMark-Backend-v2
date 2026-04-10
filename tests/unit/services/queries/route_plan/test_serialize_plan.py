from types import SimpleNamespace

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.serialize_plan import serialize_plans


def _plan(route_groups):
    return SimpleNamespace(
        id=11,
        client_id="delivery_plan:11",
        label="Plan A",
        date_strategy="single",
        start_date=None,
        end_date=None,
        created_at=None,
        updated_at=None,
        state_id=1,
        total_orders=0,
        total_weight_g=0.0,
        total_volume_cm3=0.0,
        total_item_count=0,
        item_type_counts={"Sofa": 1},
        orders=[],
        route_groups=route_groups,
    )


def test_serialize_plans_includes_route_groups_count_for_list_shape():
    route_groups = [
        SimpleNamespace(id=2, zone_geometry_snapshot={"name": "Zone B", "geometry": None}),
        SimpleNamespace(id=1, zone_geometry_snapshot={"name": "Zone A", "geometry": None}),
    ]
    serialized = serialize_plans(
        [_plan(route_groups)],
        ServiceContext(incoming_data={}, identity={}, on_query_return="list"),
    )

    assert serialized[0]["route_groups_count"] == 2
    assert "route_groups" not in serialized[0]


def test_serialize_plans_includes_detail_route_groups_summary_when_requested():
    route_groups = [
        SimpleNamespace(
            id=9,
            zone_geometry_snapshot={"name": "Zone South", "geometry": None},
            zone_id=7,
            total_orders=5,
            item_type_counts={"Lamp": 2},
            state=SimpleNamespace(id=2, name="OPEN"),
        ),
        SimpleNamespace(
            id=4,
            zone_geometry_snapshot={"name": "Zone North", "geometry": None},
            zone_id=3,
            total_orders=1,
            item_type_counts=None,
            state=None,
        ),
    ]

    serialized = serialize_plans(
        [_plan(route_groups)],
        ServiceContext(incoming_data={}, identity={}, on_query_return="list"),
        include_route_groups_summary=True,
    )

    assert serialized[0]["route_groups_count"] == 2
    assert [group["name"] for group in serialized[0]["route_groups"]] == [
        "Zone North",
        "Zone South",
    ]
    assert serialized[0]["item_type_counts"] == {"Sofa": 1}
    assert serialized[0]["route_groups"][0]["item_type_counts"] is None
    assert serialized[0]["route_groups"][1]["item_type_counts"] == {"Lamp": 2}
    assert serialized[0]["route_groups"][0]["state"] is None
    assert serialized[0]["route_groups"][1]["state"] == {"id": 2, "name": "OPEN"}
