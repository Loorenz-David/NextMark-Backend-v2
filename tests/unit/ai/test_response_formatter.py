from Delivery_app_BK.ai.response_formatter import (
    format_response,
    format_tool_trace,
    generate_blocks,
    generate_interactions,
    validate_ai_focus_warnings,
)
from Delivery_app_BK.ai.schemas import AIInteraction


def test_generate_blocks_maps_geocode_and_create_order_flow():
    tool_turns = [
        {
            "tool": "geocode_address",
            "params": {"q": "Kungsgatan 5, Stockholm"},
            "result": {
                "found": True,
                "q": "Kungsgatan 5, Stockholm",
                "formatted_address": "Kungsgatan 5, 111 56 Stockholm, Sweden",
                "address_object": {
                    "street_address": "Kungsgatan 5",
                    "postal_code": "111 56",
                    "city": "Stockholm",
                    "country": "SE",
                    "coordinates": {"lat": 59.334, "lng": 18.063},
                },
                "used_country_hint": "SE",
                "country_hint_source": "team_default",
            },
        },
        {
            "tool": "create_order",
            "params": {"client_first_name": "Anna"},
            "result": {
                "status": "created",
                "order_id": 42,
                "items_created": 0,
                "result": {
                    "created": [
                        {
                            "order": {
                                "id": 42,
                                "client_first_name": "Anna",
                                "client_address": {
                                    "street_address": "Kungsgatan 5",
                                },
                            }
                        }
                    ]
                },
            },
        },
    ]

    blocks = generate_blocks(tool_turns)

    assert [block.kind for block in blocks] == ["entity_detail", "entity_detail"]
    assert blocks[0].layout == "key_value"
    assert blocks[0].data["formatted_address"] == "Kungsgatan 5, 111 56 Stockholm, Sweden"
    assert blocks[1].entity_type == "order"
    assert blocks[1].data["id"] == 42


def test_generate_blocks_maps_list_orders_collection():
    blocks = generate_blocks([
        {
            "tool": "list_orders",
            "params": {"scheduled": False},
            "result": {
                "order": [
                    {
                        "id": 100,
                        "order_scalar_id": "100245",
                        "client_first_name": "Anna",
                        "client_last_name": "Smith",
                        "order_state_id": 3,
                    }
                ],
                "order_stats": {"total": 1},
                "order_pagination": {"has_more": False},
            },
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].kind == "entity_collection"
    assert blocks[0].entity_type == "order"
    assert blocks[0].layout == "table"
    assert blocks[0].data["total"] == 1
    assert blocks[0].data["items"][0]["client_name"] == "Anna Smith"
    assert blocks[0].data["items"][0]["reference"] == "Order 100245"
    assert blocks[0].meta["table"]["columns"] == [
        "status",
        "order_scalar_id",
        "client_name",
    ]


def test_generate_blocks_maps_single_order_object_from_list_orders():
    blocks = generate_blocks([
        {
            "tool": "list_orders",
            "params": {"q": "1056", "s": ["order_scalar_id"], "limit": 1},
            "result": {
                "order": {
                    "id": 1056,
                    "order_scalar_id": "1056",
                    "client_first_name": "Some",
                    "client_last_name": "Name",
                    "order_state_id": 1,
                    "delivery_plan_id": 129,
                },
                "order_stats": {"total": 1},
                "order_pagination": {"has_more": False},
            },
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].kind == "entity_collection"
    assert blocks[0].data["total"] == 1
    assert blocks[0].data["items"][0]["id"] == 1056
    assert blocks[0].data["items"][0]["client_name"] == "Some Name"
    assert blocks[0].meta["table"]["columns"][0] == "order_scalar_id"


def test_generate_blocks_prioritizes_client_name_for_client_search():
    blocks = generate_blocks([
        {
            "tool": "list_orders",
            "params": {"q": "ana", "s": ["client_first_name", "client_last_name"]},
            "result": {
                "order": [
                    {
                        "id": 101,
                        "order_scalar_id": "101",
                        "client_first_name": "Ana",
                        "client_last_name": "Lopez",
                        "order_state_id": 2,
                        "client_address": {"street_address": "Main St 5"},
                        "total_items": 3,
                    }
                ],
                "order_stats": {"total": 1},
                "order_pagination": {"has_more": False},
            },
        }
    ])

    assert blocks[0].meta["table"]["columns"] == [
        "client_name",
        "order_scalar_id",
        "status",
        "street_address",
    ]


def test_generate_blocks_maps_plan_and_route_tables_with_columns():
    blocks = generate_blocks([
        {
            "tool": "list_plans",
            "params": {"label": "Morning"},
            "result": {
                "route_plans": [
                    {
                        "id": 91,
                        "label": "Morning route",
                        "plan_type": "local_delivery",
                        "start_date": "2026-03-21T08:00:00Z",
                        "end_date": "2026-03-21T12:00:00Z",
                        "state_id": 2,
                        "total_orders": 4,
                    }
                ],
            },
        },
        {
            "tool": "list_routes",
            "params": {"plan_id": 91},
            "result": {
                "routes": [
                    {
                        "id": 501,
                        "route_group_id": 91,
                        "driver_id": 7,
                        "is_selected": True,
                        "stops": [{"id": 1}, {"id": 2}],
                        "route_plan": {"label": "Morning route"},
                    }
                ],
            },
        },
    ])

    assert blocks[0].layout == "table"
    assert blocks[0].meta["table"]["columns"][0] == "plan_name"
    assert blocks[0].data["items"][0]["reference"] == "Morning route (local_delivery plan)"
    assert blocks[1].layout == "table"
    assert blocks[1].meta["table"]["columns"][0] == "reference"
    assert blocks[1].data["items"][0]["reference"] == "Route for Morning route"


def test_generate_blocks_falls_back_for_unknown_tool():
    blocks = generate_blocks([
        {
            "tool": "custom_tool",
            "params": {"foo": "bar"},
            "result": {"value": 1},
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].kind == "summary"
    assert blocks[0].entity_type == "generic"
    assert blocks[0].data["tool"] == "custom_tool"


def test_format_response_uses_interactions_override():
    response = format_response(
        "thr_123",
        "I need contact details.",
        [],
        interactions_override=[
            AIInteraction(
                id="int_clarify_create_order_contact",
                kind="question",
                label="Add customer contact details",
                required=True,
                response_mode="form",
                payload={"at_least_one_of": ["client_email", "client_phone"]},
                fields=[
                    {"id": "client_email", "label": "Customer email", "type": "email"},
                    {"id": "client_phone", "label": "Customer phone", "type": "tel"},
                ],
            )
        ],
    )

    assert response.message.interactions[0].id == "int_clarify_create_order_contact"
    assert response.message.interactions[0].response_mode == "form"


def test_generate_blocks_maps_plan_creation_and_assignment():
    blocks = generate_blocks([
        {
            "tool": "create_plan",
            "params": {
                "label": "Morning route",
                "start_date": "2026-03-21T08:00:00Z",
                "end_date": "2026-03-21T12:00:00Z",
            },
            "result": {
                "plan_id": 91,
                "label": "Morning route",
                "plan_type": "local_delivery",
                "start_date": "2026-03-21T08:00:00Z",
                "end_date": "2026-03-21T12:00:00Z",
            },
        },
        {
            "tool": "assign_orders_to_plan",
            "params": {"plan_id": 91, "order_ids": [10, 11]},
            "result": {
                "status": "assigned",
                "plan_id": 91,
                "requested": 2,
                "assigned": 2,
            },
        },
    ])

    assert [block.kind for block in blocks] == ["entity_detail", "summary"]
    assert blocks[0].entity_type == "plan"
    assert blocks[0].data["id"] == 91
    assert blocks[1].data["assigned"] == 2
    assert blocks[1].data["plan_id"] == 91


def test_generate_blocks_maps_order_mutations_and_items():
    blocks = generate_blocks([
        {
            "tool": "update_order_state",
            "params": {"order_ids": [42, 43], "state_name": "Completed"},
            "result": {
                "status": "updated",
                "state": "Completed",
                "order_ids": [42, 43],
                "count": 2,
            },
        },
        {
            "tool": "update_order",
            "params": {"order_id": 42, "fields": {"client_first_name": "Anna"}},
            "result": {
                "status": "updated",
                "order_id": 42,
                "updated_fields": ["client_first_name"],
            },
        },
        {
            "tool": "add_items_to_order",
            "params": {"order_id": 42},
            "result": {
                "status": "added",
                "order_id": 42,
                "items_added": 1,
                "result": [{"id": 1, "item_type": "table"}],
            },
        },
    ])

    assert [block.kind for block in blocks] == ["summary", "entity_detail", "entity_detail"]
    assert blocks[0].data["state"] == "Completed"
    assert blocks[1].data["updated_fields"] == ["client_first_name"]
    assert blocks[2].data["items_added"] == 1


def test_generate_blocks_maps_item_search_and_plan_optimization():
    blocks = generate_blocks([
        {
            "tool": "search_item_types",
            "params": {"q": "table"},
            "result": {
                "item_types": [
                    {
                        "item_type": "table",
                        "sample_article_number": "table-ab12cd",
                        "properties_template": {"extensions": 0},
                    }
                ],
                "count": 1,
                "matched": True,
            },
        },
        {
            "tool": "optimize_plan",
            "params": {"route_plan_id": 77},
            "result": {
                "status": "optimized",
                "route_id": 501,
                "total_distance_meters": 12345,
                "total_travel_time_seconds": 3600,
            },
        },
    ])

    assert [block.kind for block in blocks] == ["entity_collection", "summary"]
    assert blocks[0].layout == "chips"
    assert blocks[0].data["items"][0]["item_type"] == "table"
    assert blocks[0].data["items"][0]["reference"] == "table (12cd)"
    assert blocks[1].data["plan_id"] == 77
    assert blocks[1].data["route_id"] == 501


def test_format_tool_trace_normalizes_list_orders_count_from_nested_stats():
    trace = format_tool_trace([
        {
            "tool": "list_orders",
            "params": {"scheduled": True},
            "result": {
                "order": [
                    {"id": 95, "order_scalar_id": 1056},
                    {"id": 94, "order_scalar_id": 1055},
                ],
                "order_stats": {"orders": {"total": 2}},
            },
        }
    ])

    assert len(trace) == 1
    assert trace[0].summary == "Found 2 orders."


def test_generate_blocks_maps_list_item_types_config_nested_shape():
    blocks = generate_blocks([
        {
            "tool": "list_item_types_config",
            "params": {"limit": 20},
            "result": {
                "count": 2,
                "item_types": {
                    "allIds": ["it_1", "it_2"],
                    "byClientId": {
                        "it_1": {"id": 1, "name": "dining chair", "properties": []},
                        "it_2": {"id": 2, "name": "sideboard", "properties": [11]},
                    },
                },
            },
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].entity_type == "item_type"
    assert blocks[0].layout == "table"
    assert blocks[0].data["total"] == 2
    assert blocks[0].data["items"][0]["name"] in {"dining chair", "sideboard"}


def test_format_response_keeps_legacy_data_while_adding_blocks():
    response = format_response(
        "thr_123",
        "Created order #42 for Anna.",
        [
            {
                "tool": "create_order",
                "params": {"client_first_name": "Anna"},
                "result": {"status": "created", "order_id": 42, "items_created": 0},
            }
        ],
        data={"legacy": True},
    )

    assert response.thread_id == "thr_123"
    assert response.message.content == "Created order #42 for Anna."
    assert response.message.data == {"legacy": True}
    assert len(response.message.blocks) == 1
    assert response.message.blocks[0].kind == "entity_detail"


def test_format_response_sets_intent_policy_and_rendering_hints_with_blocks():
    response = format_response(
        "thr_123",
        "I found 2 orders.\n- ORD-1 is late\n- ORD-2 is unassigned",
        [
            {
                "tool": "list_orders",
                "params": {"scheduled": False},
                "result": {
                    "count": 2,
                    "orders": [
                        {"id": "ORD-1", "order_scalar_id": "ORD-1", "order_state_id": 1, "is_late": True, "route_plan_id": 10},
                        {"id": "ORD-2", "order_scalar_id": "ORD-2", "order_state_id": 1, "is_late": False, "route_plan_id": None},
                    ],
                },
            }
        ],
    )

    assert response.message.intent == "summary_with_blocks"
    assert response.message.narrative_policy == "no_enumeration"
    assert response.message.rendering_hints["has_blocks"] is True
    assert "ORD-1 is late" in response.message.content
    assert "ORD-2 is unassigned" in response.message.content


def test_format_response_full_enumeration_preserves_list_lines():
    response = format_response(
        "thr_123",
        "Summary\n- Row 1\n- Row 2",
        [],
        narrative_policy_override="full_enumeration",
    )

    assert response.message.narrative_policy == "full_enumeration"
    assert "- Row 1" in response.message.content


def test_format_response_adds_markdown_structure_for_plain_content_with_blocks():
    response = format_response(
        "thr_123",
        "There are currently 4 orders in the system. Two are draft. One is ready. One is completed.",
        [
            {
                "tool": "list_orders",
                "params": {},
                "result": {
                    "count": 4,
                    "orders": [
                        {"id": 1, "order_scalar_id": "1056", "order_state_id": 1},
                        {"id": 2, "order_scalar_id": "1055", "order_state_id": 1},
                    ],
                },
            }
        ],
    )

    assert response.message.content.startswith("### Snapshot")
    assert "#### Highlights" in response.message.content
    assert "- Two are draft." in response.message.content


def test_generate_actions_keeps_filters_but_omits_navigate_actions():
    response = format_response(
        "thr_123",
        "Found matching scheduled orders.",
        [
            {
                "tool": "list_orders",
                "params": {"q": "Stockholm", "scheduled": True},
                "result": {
                    "count": 2,
                    "orders": [
                        {"id": 1, "order_scalar_id": "1054", "order_state_id": 2, "route_plan_id": 10},
                        {"id": 2, "order_scalar_id": "1053", "order_state_id": 2, "route_plan_id": 11},
                    ],
                },
            }
        ],
    )

    assert all(action.type != "navigate" for action in response.message.actions)
    assert any(action.type == "apply_order_filters" for action in response.message.actions)


def test_format_response_uses_validated_presentation_hint_columns_for_orders():
    response = format_response(
        "thr_123",
        "The following orders contain items.",
        [
            {
                "tool": "list_orders",
                "params": {},
                "result": {
                    "count": 2,
                    "orders": [
                        {"id": 1, "order_scalar_id": "1054", "order_state_id": 5, "total_items": 11},
                        {"id": 2, "order_scalar_id": "1053", "order_state_id": 1, "total_items": 0},
                    ],
                },
            }
        ],
        presentation_hints_override={
            "blocks": [
                {"entity_type": "order", "columns": ["reference", "total_items", "status", "not_allowed"]}
            ]
        },
    )

    columns = response.message.blocks[0].meta["table"]["columns"]
    assert columns == ["reference", "total_items", "status"]
    assert response.message.blocks[0].data["items"][0]["total_items"] == 11


def test_format_response_uses_query_fallback_columns_for_item_questions_without_hints():
    response = format_response(
        "thr_123",
        "These are orders that contain items.",
        [
            {
                "tool": "list_orders",
                "params": {},
                "result": {
                    "count": 2,
                    "orders": [
                        {"id": 1, "order_scalar_id": "1054", "order_state_id": 5, "total_items": 11},
                        {"id": 2, "order_scalar_id": "1053", "order_state_id": 1, "total_items": 0},
                    ],
                },
            }
        ],
        user_query_override="what orders contain items?",
    )

    columns = response.message.blocks[0].meta["table"]["columns"]
    assert columns == ["reference", "total_items", "status", "street_address"]


def test_format_response_keeps_existing_markdown_content_unchanged():
    original = "### Snapshot\n\nThere are **2 orders**."
    response = format_response(
        "thr_123",
        original,
        [
            {
                "tool": "list_orders",
                "params": {},
                "result": {
                    "count": 2,
                    "orders": [
                        {"id": 1, "order_scalar_id": "1056", "order_state_id": 1},
                        {"id": 2, "order_scalar_id": "1055", "order_state_id": 7},
                    ],
                },
            }
        ],
    )

    assert response.message.content == original


def test_generate_blocks_adds_ai_focus_for_late_or_unassigned_orders():
    response = format_response(
        "thr_123",
        "Found issues in orders.",
        [
            {
                "tool": "list_orders",
                "params": {},
                "result": {
                    "orders": [
                        {"id": "ORD-11", "order_scalar_id": "ORD-11", "order_state_id": 1, "is_late": True, "route_plan_id": 20},
                        {"id": "ORD-12", "order_scalar_id": "ORD-12", "order_state_id": 1, "is_late": False, "route_plan_id": None},
                    ],
                    "count": 2,
                },
            }
        ],
    )

    block = response.message.blocks[0]
    ai_focus = block.data.get("ai_focus")
    assert ai_focus is not None
    assert sorted(ai_focus["focus_entity_ids"]) == ["ORD-11", "ORD-12"]
    assert ai_focus["focus_counts"]["late"] == 1
    assert ai_focus["focus_counts"]["unassigned"] == 1


def test_format_response_emits_warning_when_ai_focus_references_missing_entities():
    rebuilt = format_response(
        "thr_123",
        "Found issues in orders.",
        [
            {
                "tool": "list_orders",
                "params": {},
                "result": {
                    "orders": [{"id": "ORD-1", "order_scalar_id": "ORD-1", "order_state_id": 1}],
                    "count": 1,
                },
            }
        ],
    )
    rebuilt.message.blocks[0].data["ai_focus"] = {"focus_entity_ids": ["ORD-1", "ORD-2"]}
    warnings = validate_ai_focus_warnings(rebuilt.message.blocks)

    assert len(warnings) == 1
    assert warnings[0].code == "AI_FOCUS_MISMATCH"
    assert warnings[0].message == "ai_focus references entities not present in block items."
    assert warnings[0].meta["missing_entity_ids"] == ["ORD-2"]


def test_format_response_uses_ai_led_plan_focus_from_narrative_and_keeps_missing_ids():
    response = format_response(
        "thr_123",
        "Plan 92 and plan 999 need attention.",
        [
            {
                "tool": "list_plans",
                "params": {},
                "result": {
                    "route_plans": [
                        {"id": 91, "label": "Morning", "plan_type": "local_delivery", "state_id": 2},
                        {"id": 92, "label": "Evening", "plan_type": "local_delivery", "state_id": 2},
                    ],
                    "count": 2,
                },
            }
        ],
        operation_name="list_plans",
    )

    ai_focus = response.message.blocks[0].data["ai_focus"]
    assert "92" in ai_focus["focus_entity_ids"]
    assert "999" in ai_focus["focus_entity_ids"]
    assert response.message.typed_warnings
    assert response.message.typed_warnings[0].code == "AI_FOCUS_MISMATCH"
    assert response.message.typed_warnings[0].meta["missing_entity_ids"] == ["999"]


def test_format_response_uses_ai_led_route_focus_from_narrative():
    response = format_response(
        "thr_123",
        "Route 501 should be prioritized.",
        [
            {
                "tool": "list_routes",
                "params": {"plan_id": 91},
                "result": {
                    "routes": [
                        {
                            "id": 501,
                            "route_plan": {"label": "Morning route"},
                            "driver_id": 7,
                            "is_selected": True,
                            "stops": [{"id": 1}],
                        }
                    ],
                    "count": 1,
                },
            }
        ],
        operation_name="list_routes",
    )

    ai_focus = response.message.blocks[0].data["ai_focus"]
    assert "501" in ai_focus["focus_entity_ids"]


def test_generate_interactions_no_results_on_error():
    """Phase 1: errors should not generate interactions."""
    tool_turns = [
        {
            "tool": "list_orders",
            "params": {},
            "result": {
                "error": "Database connection failed",
            },
        }
    ]

    interactions = generate_interactions(tool_turns)

    # Should have no interactions on error
    assert len(interactions) == 0


def test_generate_interactions_adds_plan_type_question_when_plan_types_are_ambiguous():
    tool_turns = [
        {
            "tool": "list_plans",
            "params": {},
            "result": {
                    "route_plans": [
                    {"id": 1, "label": "A", "plan_type": "local_delivery"},
                    {"id": 2, "label": "B", "plan_type": "international_shipping"},
                ],
                "count": 2,
            },
        }
    ]

    interactions = generate_interactions(tool_turns)

    question = next((i for i in interactions if i.kind == "question"), None)
    assert question is not None
    assert question.required is True
    assert question.response_mode == "select"
    assert sorted(opt["id"] for opt in (question.options or [])) == [
        "international_shipping",
        "local_delivery",
    ]


def test_generate_interactions_adds_driver_question_when_routes_have_multiple_drivers():
    tool_turns = [
        {
            "tool": "list_routes",
            "params": {},
            "result": {
                "routes": [
                    {"id": 1, "driver_id": 10, "driver_name": "Alice"},
                    {"id": 2, "driver_id": 11, "driver_name": "Bob"},
                ],
                "count": 2,
            },
        }
    ]

    interactions = generate_interactions(tool_turns)

    question = next((i for i in interactions if i.id == "int_question_driver"), None)
    assert question is not None
    assert question.kind == "question"
    assert question.required is True
    assert question.response_mode == "select"
    assert sorted(option["label"] for option in (question.options or [])) == ["Alice", "Bob"]


def test_generate_interactions_adds_confirm_for_large_order_state_update():
    tool_turns = [
        {
            "tool": "update_order_state",
            "params": {"order_ids": [1, 2, 3, 4, 5, 6], "state_name": "Completed"},
            "result": {"count": 6, "state": "Completed", "order_ids": [1, 2, 3, 4, 5, 6]},
        }
    ]

    interactions = generate_interactions(tool_turns)

    confirm = next((i for i in interactions if i.kind == "confirm"), None)
    assert confirm is not None
    assert confirm.required is True
    assert confirm.response_mode == "confirm"
    assert confirm.payload.get("target_count") == 6
    assert confirm.payload.get("operation") == "update_order_state"


def test_generate_interactions_adds_confirm_for_large_assign_batch():
    tool_turns = [
        {
            "tool": "assign_orders_to_plan",
            "params": {"plan_id": 99, "order_ids": list(range(1, 55))},
            "result": {"assigned": 54, "plan_id": 99},
        }
    ]

    interactions = generate_interactions(tool_turns)

    confirm = next((i for i in interactions if i.id == "int_confirm_assign_orders"), None)
    assert confirm is not None
    assert confirm.kind == "confirm"
    assert confirm.required is True
    assert confirm.payload.get("plan_id") == 99


def test_generate_blocks_maps_analytics_snapshot_into_kpi_trend_breakdown_blocks():
    blocks = generate_blocks([
        {
            "tool": "get_analytics_snapshot",
            "params": {"timeframe": "7d"},
            "result": {
                "metrics": {
                    "total_orders": 120,
                    "scheduled_rate": 0.82,
                    "completion_rate": 0.77,
                    "failed_orders": 8,
                },
                "trends": [
                    {"date": "2026-03-15", "orders_created": 14},
                    {"date": "2026-03-16", "orders_created": 18},
                ],
                "breakdowns": [
                    {
                        "dimension": "scheduled_status",
                        "values": [
                            {"label": "scheduled", "count": 98},
                            {"label": "unscheduled", "count": 22},
                        ],
                    }
                ],
            },
        }
    ])

    assert [block.entity_type for block in blocks] == ["analytics_kpi", "analytics_trend", "analytics_breakdown"]
    assert blocks[0].data["items"][0]["name"] == "total_orders"
    assert blocks[1].data["items"][0]["date"] == "2026-03-15"
    assert blocks[2].data["items"][0]["dimension"] == "scheduled_status"


def test_format_tool_trace_summarizes_analytics_snapshot():
    trace = format_tool_trace([
        {
            "tool": "get_analytics_snapshot",
            "params": {"timeframe": "7d"},
            "result": {"metrics": {"total_orders": 42}},
        }
    ])

    assert trace[0].summary == "Analytics snapshot ready for 42 orders."


def test_format_response_adds_statistical_output_insight_and_warning_blocks():
    response = format_response(
        "thr_123",
        "Late deliveries increased in the selected window.",
        [],
        data={
            "statistical_output": {
                "summary": "Late deliveries increased in the selected window.",
                "key_metrics": [
                    {"name": "late_deliveries", "value": 18.0, "delta": 4.0},
                ],
                "insights": [
                    {
                        "type": "correlation",
                        "description": "Higher unscheduled share coincides with more late deliveries.",
                        "confidence": 0.71,
                    }
                ],
                "warnings": ["Correlation only; causation is not proven."],
                "confidence_score": 0.78,
            }
        },
    )

    entity_types = [block.entity_type for block in response.message.blocks]
    assert "analytics_insight" in entity_types
    assert "analytics_warning" in entity_types


# ---------------------------------------------------------------------------
# Contract tests: plain list shape from on_query_return="list"
# ---------------------------------------------------------------------------

def test_generate_blocks_list_plans_plain_list_shape():
    """list_plans result with plain list under 'route_plan' key produces non-empty items."""
    blocks = generate_blocks([
        {
            "tool": "list_plans",
            "params": {},
            "result": {
                "route_plan": [
                    {"id": 173, "label": "March run", "plan_type": "local_delivery", "state_id": 1, "total_orders": 11},
                ],
                "route_plan_stats": {"plans": {"total": 1}},
                "route_plan_pagination": {"has_more": False},
            },
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].kind == "entity_collection"
    assert blocks[0].entity_type == "plan"
    assert blocks[0].data["total"] == 1
    assert len(blocks[0].data["items"]) == 1
    assert blocks[0].data["items"][0]["id"] == 173
    assert blocks[0].data["items"][0]["plan_name"] == "March run"
    assert blocks[0].data["items"][0]["total_orders"] == 11


def test_format_tool_trace_list_plans_plain_list_uses_stats_count():
    """_summarize for list_plans reads count from route_plan_stats, not from empty fallback."""
    trace = format_tool_trace([
        {
            "tool": "list_plans",
            "params": {},
            "result": {
                "route_plan": [
                    {"id": 173, "label": "March run", "plan_type": "local_delivery"},
                ],
                "route_plan_stats": {"plans": {"total": 1}},
            },
        }
    ])

    assert trace[0].summary == "Found 1 plan."


def test_generate_blocks_list_orders_plain_list_shape():
    """list_orders result with plain list under 'order' key produces non-null item fields."""
    blocks = generate_blocks([
        {
            "tool": "list_orders",
            "params": {},
            "result": {
                "order": [
                    {
                        "id": 196,
                        "order_scalar_id": "12345",
                        "client_first_name": "Maria",
                        "client_last_name": "Garcia",
                        "order_state_id": 2,
                        "delivery_plan_id": 173,
                    }
                ],
                "order_stats": {"orders": {"total": 1}},
            },
        }
    ])

    assert len(blocks) == 1
    item = blocks[0].data["items"][0]
    assert item["id"] == 196
    assert item["client_name"] == "Maria Garcia"
    assert item["reference"] == "Order 12345"
    assert blocks[0].data["total"] == 1


def test_generate_blocks_ai_focus_excludes_none_id_rows():
    """Orders with id=None must not produce 'None' string in focus_entity_ids."""
    blocks = generate_blocks([
        {
            "tool": "list_orders",
            "params": {},
            "result": {
                "order": [
                    {"id": None, "order_scalar_id": None, "order_state_id": 1, "delivery_plan_id": None},
                    {"id": 200, "order_scalar_id": "200", "order_state_id": 1, "delivery_plan_id": None},
                ],
                "order_stats": {"total": 2},
            },
        }
    ])

    item_ids = [item["id"] for item in blocks[0].data["items"]]
    # id=None row is included in items but must not produce "None" in focus_entity_ids
    ai_focus = blocks[0].data.get("ai_focus") or {}
    focus_ids = ai_focus.get("focus_entity_ids") or []
    assert "None" not in focus_ids
    assert "200" in focus_ids


def test_generate_blocks_list_item_types_config_plain_list_shape():
    """list_item_types_config with plain list under 'item_types' key works correctly."""
    blocks = generate_blocks([
        {
            "tool": "list_item_types_config",
            "params": {"limit": 20},
            "result": {
                "count": 2,
                "item_types": [
                    {"id": 1, "name": "dining chair", "properties": []},
                    {"id": 2, "name": "sideboard", "properties": [11]},
                ],
            },
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].entity_type == "item_type"
    assert blocks[0].data["total"] == 2
    assert len(blocks[0].data["items"]) == 2
    names = {item["name"] for item in blocks[0].data["items"]}
    assert names == {"dining chair", "sideboard"}


def test_generate_blocks_list_item_properties_config_plain_list_shape():
    """list_item_properties_config with plain list emits an entity_property block."""
    blocks = generate_blocks([
        {
            "tool": "list_item_properties_config",
            "params": {"limit": 10},
            "result": {
                "count": 2,
                "item_properties": [
                    {"id": 1, "name": "color", "field_type": "text", "required": False},
                    {"id": 2, "name": "weight_kg", "field_type": "number", "required": True},
                ],
            },
        }
    ])

    assert len(blocks) == 1
    assert blocks[0].entity_type == "item_property"
    assert blocks[0].layout == "table"
    assert blocks[0].data["total"] == 2
    assert blocks[0].meta["table"]["columns"] == ["name", "field_type", "required"]
    names = {item["name"] for item in blocks[0].data["items"]}
    assert names == {"color", "weight_kg"}


def test_format_response_prefers_narrative_blocks_over_raw_analytics_blocks():
    response = format_response(
        "thr_123",
        "Late deliveries increased in the selected window.",
        [
            {
                "tool": "get_analytics_snapshot",
                "params": {"timeframe": "7d"},
                "result": {
                    "metrics": {"total_orders": 120, "late_deliveries": 18},
                    "trends": [{"date": "2026-03-15", "late_deliveries": 7}],
                    "breakdowns": [{"dimension": "scheduled_status", "values": []}],
                },
            }
        ],
        data={
            "blocks": [
                {"type": "text", "title": "Context", "text": "Late deliveries rose after unscheduled share increased."},
                {
                    "type": "analytics_kpi",
                    "title": "Late Deliveries KPI",
                    "metric_name": "late_deliveries",
                    "value": 18,
                    "display_value": "18",
                    "delta": 4,
                    "confidence_score": 0.71,
                },
                {
                    "type": "analytics_trend",
                    "title": "Late deliveries over time",
                    "description": "Consistent rise across the week.",
                    "direction": "up",
                },
            ],
            "confidence_score": 0.78,
        },
    )

    assert [block.kind for block in response.message.blocks] == ["summary", "analytics_kpi", "analytics_trend"]
    assert response.message.blocks[0].title == "Context"
    assert response.message.blocks[0].data["text"] == "Late deliveries rose after unscheduled share increased."
    assert response.message.blocks[1].title == "Late Deliveries KPI"
    assert response.message.blocks[1].meta["schema_version"] == 1
    assert response.message.rendering_hints["suppress_raw_data_preview"] is True


def test_format_response_maps_generic_analytics_layout_blocks():
    response = format_response(
        "thr_123",
        "Performance highlights are shown below.",
        [
            {
                "tool": "get_analytics_snapshot",
                "params": {"timeframe": "30d"},
                "result": {"metrics": {"total_orders": 1842}},
            }
        ],
        data={
            "blocks": [
                {
                    "type": "analytics",
                    "layout": "metric_grid",
                    "title": "Core Metrics",
                    "subtitle": "Last 30 days",
                    "data": {
                        "metrics": [
                            {
                                "id": "orders_total",
                                "label": "Orders",
                                "value": 1842,
                                "display_value": "1,842",
                                "change_label": "+12.4% vs prior period",
                                "trend": "up",
                                "value_type": "integer",
                            }
                        ]
                    },
                    "chartType": "line",
                },
                {
                    "type": "analytics",
                    "layout": "table",
                    "title": "Corridor Breakdown",
                    "data": {
                        "columns": [
                            {"id": "corridor", "label": "Corridor"},
                            {"id": "orders", "label": "Orders"},
                        ],
                        "rows": [
                            {"id": "r1", "corridor": "North Hub", "orders": 774},
                        ],
                    },
                },
            ],
        },
    )

    assert len(response.message.blocks) == 2
    assert response.message.blocks[0].kind == "analytics"
    assert response.message.blocks[0].layout == "metric_grid"
    assert response.message.blocks[0].title == "Core Metrics"
    assert response.message.blocks[0].subtitle == "Last 30 days"
    assert response.message.blocks[0].meta["chartType"] == "line"
    assert response.message.blocks[0].meta["schema_version"] == 1
    assert response.message.blocks[1].layout == "table"


def test_format_response_maps_statistics_warning_strings_to_typed_warnings():
    response = format_response(
        "thr_123",
        "Summary",
        [{"tool": "get_analytics_snapshot", "params": {}, "result": {"metrics": {"total_orders": 12}}}],
        data={
            "blocks": [{"type": "text", "text": "Sample"}],
            "warnings": [
                "Sample payload generated for frontend visualization.",
                "Limited timeframe selected.",
            ],
        },
    )

    codes = [warning.code for warning in response.message.typed_warnings]
    assert codes.count("STATISTICS_WARNING") == 2
    assert response.message.typed_warnings[0].meta["source"] == "narrative_statistics"


def test_format_response_honors_intent_and_policy_from_data_payload():
    response = format_response(
        "thr_123",
        "This text is intentionally hidden because intent is blocks_only.",
        [{"tool": "get_analytics_snapshot", "params": {}, "result": {"metrics": {"total_orders": 10}}}],
        data={
            "intent": "blocks_only",
            "narrative_policy": "no_enumeration",
            "blocks": [{"type": "text", "text": "Throughput reading."}],
        },
    )

    assert response.message.intent == "blocks_only"
    assert response.message.narrative_policy == "no_enumeration"


# ---------------------------------------------------------------------------
# Risk brief block helper tests
# ---------------------------------------------------------------------------

def _make_analytics_turn(metrics: dict) -> dict:
    return {"tool": "get_analytics_snapshot", "params": {}, "result": {"metrics": metrics}}


def test_build_risk_brief_block_returns_none_when_depth_is_none():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    assert _build_risk_brief_block([], None) is None
    assert _build_risk_brief_block([], "none") is None


def test_build_risk_brief_block_returns_none_when_no_analytics_turn():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [{"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}]}}]
    assert _build_risk_brief_block(turns, "risk_brief") is None


def test_build_risk_brief_block_returns_high_risk_when_failed_orders_present():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [_make_analytics_turn({"total_orders": 10, "failed_orders": 3, "unscheduled_orders": 0, "completion_rate": 0.70})]
    block = _build_risk_brief_block(turns, "risk_brief")

    assert block is not None
    assert block.kind == "summary"
    assert block.entity_type == "analytics_risk"
    assert block.data["risk_level"] == "high"
    assert "failed" in block.data["text"].lower()


def test_build_risk_brief_block_returns_high_risk_when_completion_rate_below_85():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [_make_analytics_turn({"total_orders": 20, "failed_orders": 0, "unscheduled_orders": 0, "completion_rate": 0.80})]
    block = _build_risk_brief_block(turns, "risk_brief")

    assert block is not None
    assert block.data["risk_level"] == "high"


def test_build_risk_brief_block_returns_medium_risk_when_unscheduled_present():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [_make_analytics_turn({"total_orders": 15, "failed_orders": 0, "unscheduled_orders": 4, "completion_rate": 0.90})]
    block = _build_risk_brief_block(turns, "risk_brief")

    assert block is not None
    assert block.data["risk_level"] == "medium"


def test_build_risk_brief_block_returns_low_risk_when_metrics_healthy():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [_make_analytics_turn({"total_orders": 15, "failed_orders": 0, "unscheduled_orders": 0, "completion_rate": 0.97})]
    block = _build_risk_brief_block(turns, "risk_brief")

    assert block is not None
    assert block.data["risk_level"] == "low"
    assert "stable" in block.data["text"].lower()


def test_build_risk_brief_block_works_for_diagnostic_depth():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [_make_analytics_turn({"total_orders": 5, "failed_orders": 1, "unscheduled_orders": 0, "completion_rate": 0.80})]
    block = _build_risk_brief_block(turns, "diagnostic")

    assert block is not None
    assert block.data["insight_depth"] == "diagnostic"


def test_build_risk_brief_block_uses_last_analytics_snapshot_turn():
    from Delivery_app_BK.ai.response_formatter import _build_risk_brief_block

    turns = [
        _make_analytics_turn({"total_orders": 5, "failed_orders": 5, "completion_rate": 0.0}),
        _make_analytics_turn({"total_orders": 20, "failed_orders": 0, "unscheduled_orders": 0, "completion_rate": 0.97}),
    ]
    block = _build_risk_brief_block(turns, "risk_brief")

    # Should use the LAST analytics turn (low risk), not the first (high risk)
    assert block is not None
    assert block.data["risk_level"] == "low"


def test_format_response_prepends_risk_block_when_insight_depth_set():
    tool_turns = [
        {"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}], "order_stats": {"total": 1}, "order_pagination": {"has_more": False}}},
        _make_analytics_turn({"total_orders": 10, "failed_orders": 2, "unscheduled_orders": 0, "completion_rate": 0.80}),
    ]

    response = format_response(
        "thr_123",
        "Here are today's orders.",
        tool_turns,
        data={"insight_depth": "risk_brief"},
    )

    blocks = response.message.blocks
    assert len(blocks) >= 1
    risk_blocks = [b for b in blocks if getattr(b, "entity_type", None) == "analytics_risk"]
    assert len(risk_blocks) == 1
    # Risk block must appear before order blocks
    risk_index = blocks.index(risk_blocks[0])
    order_blocks = [b for b in blocks if getattr(b, "entity_type", None) == "order"]
    if order_blocks:
        assert risk_index < blocks.index(order_blocks[0])


def test_format_response_skips_risk_block_when_no_analytics_snapshot_turn():
    tool_turns = [
        {"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}], "order_stats": {"total": 1}, "order_pagination": {"has_more": False}}},
    ]

    response = format_response(
        "thr_123",
        "Here are today's orders.",
        tool_turns,
        data={"insight_depth": "risk_brief"},
    )

    risk_blocks = [b for b in response.message.blocks if getattr(b, "entity_type", None) == "analytics_risk"]
    assert len(risk_blocks) == 0


def test_format_response_skips_risk_block_when_insight_depth_is_none():
    tool_turns = [
        _make_analytics_turn({"total_orders": 10, "failed_orders": 5, "completion_rate": 0.50}),
    ]

    response = format_response(
        "thr_123",
        "Analytics result.",
        tool_turns,
        data={"insight_depth": "none"},
    )

    risk_blocks = [b for b in response.message.blocks if getattr(b, "entity_type", None) == "analytics_risk"]
    assert len(risk_blocks) == 0

