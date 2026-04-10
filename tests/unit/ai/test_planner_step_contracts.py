from Delivery_app_BK.ai.schemas import (
    PlannerClarifyStep,
    PlannerFinalStep,
    PlannerIntentStep,
    PlannerToolStep,
    parse_planner_step,
)


def test_parse_planner_step_validates_intent_contract():
    step = parse_planner_step(
        {
            "type": "intent",
            "operation": "create_order",
            "needs_clarification": True,
            "reason": "missing contact details",
        }
    )

    assert isinstance(step, PlannerIntentStep)
    assert step.operation == "create_order"
    assert step.needs_clarification is True


def test_parse_planner_step_validates_clarify_contract_with_interaction():
    step = parse_planner_step(
        {
            "type": "clarify",
            "message": "I need contact details.",
            "interaction": {
                "id": "int_clarify_create_order_contact",
                "kind": "question",
                "label": "Add customer contact details",
                "required": True,
                "response_mode": "form",
                "payload": {"at_least_one_of": ["client_email", "client_phone"]},
                "fields": [
                    {"id": "client_email", "label": "Customer email", "type": "email"},
                    {"id": "client_phone", "label": "Customer phone", "type": "tel"},
                ],
            },
        }
    )

    assert isinstance(step, PlannerClarifyStep)
    assert step.interaction.id == "int_clarify_create_order_contact"
    assert step.interaction.response_mode == "form"


def test_parse_planner_step_validates_tool_contract():
    step = parse_planner_step(
        {
            "type": "tool",
            "tool": "create_order",
            "parameters": {"client_email": "ana@example.com"},
        }
    )

    assert isinstance(step, PlannerToolStep)
    assert step.tool == "create_order"
    assert step.parameters["client_email"] == "ana@example.com"


def test_parse_planner_step_validates_final_contract_with_presentation_hints():
    step = parse_planner_step(
        {
            "type": "final",
            "message": "Found matching orders.",
            "presentation_hints": {
                "blocks": [
                    {"entity_type": "order", "columns": ["reference", "total_items", "status"]}
                ]
            },
        }
    )

    assert isinstance(step, PlannerFinalStep)
    assert step.presentation_hints is not None
    assert step.presentation_hints.blocks[0].entity_type == "order"
    assert step.presentation_hints.blocks[0].columns == ["reference", "total_items", "status"]