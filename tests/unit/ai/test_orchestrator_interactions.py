from Delivery_app_BK.ai.orchestrator import handle_ai_request_with_thread
from Delivery_app_BK.ai.capabilities.base import CapabilityProfile
from Delivery_app_BK.ai.schemas import (
    AIInteraction,
    AIThreadTurn,
    PlannerClarifyStep,
    PlannerFinalStep,
    PlannerIntentStep,
    PlannerToolStep,
)
from Delivery_app_BK.ai.stages import CLARIFY_STAGE, EXECUTE_STAGE, INTENT_STAGE
from Delivery_app_BK.services.context import ServiceContext


class _DummyProvider:
    name = "dummy"

    def complete(self, system: str, user: str) -> str:
        return ""


def test_handle_ai_request_short_circuits_when_confirm_is_rejected(monkeypatch):
    prior_turns = [
        AIThreadTurn(
            id="turn1",
            thread_id="thr_123",
            role="assistant",
            content="Update 10 orders?",
            created_at="2026-03-21T12:00:00Z",
            awaiting_response=True,
            interaction_kind="confirm",
            interaction_id="int_confirm_update_order_state",
        )
    ]

    # Should not reach planner for rejected confirm.
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.get_next_step",
        lambda *args, **kwargs: {"type": "final", "message": "unexpected"},
    )

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="cancel",
        prior_turns=prior_turns,
        provider=_DummyProvider(),
        system_prompt="",
        interaction_response_payload={
            "__interaction_response__": "int_confirm_update_order_state",
            "confirm_accepted": False,
        },
    )

    assert result.success is True
    assert result.tool_turns == []
    assert result.final_message == "Cancelled by user. No changes were applied."
    assert result.data == {
        "interaction_cancelled": True,
        "interaction_kind": "confirm",
        "interaction_id": "int_confirm_update_order_state",
    }


def test_handle_ai_request_replays_structured_interaction_form_into_history(monkeypatch):
    captured = {}

    prior_turns = [
        AIThreadTurn(
            id="turn_user_form",
            thread_id="thr_123",
            role="user",
            content="Clarification form submitted",
            created_at="2026-03-21T12:30:00Z",
            interaction_response_id="int_clarify_create_order",
            interaction_form={
                "client_address": "Kungsgatan 5, Stockholm",
                "client_phone": "+46 70 123 45 67",
            },
        )
    ]

    def _fake_get_next_step(user_input, history, provider, system_prompt=None):
        captured["history"] = history
        return {"type": "final", "message": "ok"}

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _fake_get_next_step)

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="Clarification form submitted",
        prior_turns=prior_turns,
        provider=_DummyProvider(),
        system_prompt="",
    )

    assert result.success is True
    assert result.final_message == "ok"
    assert captured["history"][0]["role"] == "user"
    assert '"type": "interaction_response"' in captured["history"][0]["content"]
    assert '"interaction_id": "int_clarify_create_order"' in captured["history"][0]["content"]
    assert '"client_phone": "+46 70 123 45 67"' in captured["history"][0]["content"]
    assert '"normalized_facts": {"client_primary_phone": {"prefix": "+46", "number": "701234567"}, "client_phone_raw": "+46 70 123 45 67"}' in captured["history"][0]["content"]


def test_handle_ai_request_returns_clarify_result_before_execution(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {}},
    )
    captured = {"prompts": []}

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    def _fake_get_next_step(user_input, history, provider, system_prompt=None):
        captured["prompts"].append(system_prompt)
        if system_prompt == "intent-prompt":
            return PlannerIntentStep(type="intent", operation="create_order", needs_clarification=True)
        if system_prompt == "clarify-prompt":
            return PlannerClarifyStep(
                type="clarify",
                message="I need a way to contact the customer before I create the order.",
                interaction=AIInteraction(
                    id="int_clarify_create_order_contact",
                    kind="question",
                    label="Add customer contact details",
                    required=True,
                    response_mode="form",
                    payload={
                        "operation": "create_order",
                        "question_id": "q_create_order_contact",
                        "at_least_one_of": ["client_email", "client_phone"],
                    },
                    fields=[
                        {"id": "client_email", "label": "Customer email", "type": "email"},
                        {"id": "client_phone", "label": "Customer phone", "type": "tel"},
                    ],
                    hint="Provide an email address, a phone number, or both.",
                ),
            )
        raise AssertionError(f"Unexpected prompt: {system_prompt}")

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _fake_get_next_step)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.execute_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("execute_tool should not run during clarify")),
    )

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="create an order for Ana",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.tool_turns == []
    assert result.reuse_recent_tool_turns is False
    assert result.interactions[0].id == "int_clarify_create_order_contact"
    assert result.interactions[0].response_mode == "form"
    assert result.data == {"stage": CLARIFY_STAGE, "operation": "create_order"}
    assert captured["prompts"] == ["intent-prompt", "clarify-prompt"]


def test_handle_ai_request_returns_clarify_result_for_user_config(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="user_config",
        description="user-config",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    def _fake_get_next_step(user_input, history, provider, system_prompt=None):
        if system_prompt == "intent-prompt":
            return PlannerIntentStep(type="intent", operation="item_taxonomy_config", needs_clarification=True)
        if system_prompt == "clarify-prompt":
            return PlannerClarifyStep(
                type="clarify",
                message="I need details before I can propose your item taxonomy.",
                interaction=AIInteraction(
                    id="int_clarify_user_config_scope",
                    kind="question",
                    label="Confirm taxonomy scope",
                    required=True,
                    response_mode="form",
                    payload={
                        "operation": "item_taxonomy_config",
                        "question_id": "q_user_config_scope",
                    },
                    fields=[
                        {"id": "catalog_scope", "label": "Catalog scope", "type": "text", "required": True},
                    ],
                ),
            )
        raise AssertionError(f"Unexpected prompt: {system_prompt}")

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _fake_get_next_step)

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="configure furniture item types",
        prior_turns=[],
        capability_name="user_config",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.tool_turns == []
    assert result.reuse_recent_tool_turns is False
    assert result.interactions[0].id == "int_clarify_user_config_scope"
    assert result.data == {"stage": CLARIFY_STAGE, "operation": "item_taxonomy_config"}


def test_handle_ai_request_execute_stage_returns_clarify_interaction(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="user_config",
        description="user-config",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    steps = iter(
        [
            PlannerIntentStep(type="intent", operation="item_taxonomy_config", needs_clarification=False),
            PlannerClarifyStep(
                type="clarify",
                message="Here is a draft proposal. Approve to apply changes.",
                interaction=AIInteraction(
                    id="int_confirm_user_config_apply",
                    kind="confirm",
                    label="Apply item taxonomy proposal",
                    required=True,
                    response_mode="confirm",
                    payload={"operation": "item_taxonomy_config", "proposal_id": "p_1"},
                ),
            ),
        ]
    )
    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", lambda *args, **kwargs: next(steps))

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="apply this taxonomy",
        prior_turns=[],
        capability_name="user_config",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.final_message == "Here is a draft proposal. Approve to apply changes."
    assert result.reuse_recent_tool_turns is False
    assert result.interactions[0].id == "int_confirm_user_config_apply"
    assert result.data == {"stage": CLARIFY_STAGE}


def test_handle_ai_request_statistics_missing_timeframe_triggers_clarify(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="statistics",
        description="statistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"get_analytics_snapshot": lambda ctx, timeframe="7d": {}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    def _fake_get_next_step(user_input, history, provider, system_prompt=None):
        if system_prompt == "intent-prompt":
            return PlannerIntentStep(type="intent", operation="analyze_metrics", needs_clarification=True)
        if system_prompt == "clarify-prompt":
            return PlannerClarifyStep(
                type="clarify",
                message="Please choose a timeframe for the analytics view.",
                interaction=AIInteraction(
                    id="int_clarify_statistics_timeframe",
                    kind="question",
                    label="Choose a timeframe",
                    required=True,
                    response_mode="select",
                    payload={"operation": "analyze_metrics", "fallback_timeframe": "last_7_days"},
                    options=[
                        {"id": "24h", "label": "Last 24 hours"},
                        {"id": "7d", "label": "Last 7 days"},
                        {"id": "30d", "label": "Last 30 days"},
                    ],
                ),
            )
        raise AssertionError(f"Unexpected prompt: {system_prompt}")

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _fake_get_next_step)

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="show performance",
        prior_turns=[],
        capability_name="statistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.tool_turns == []
    assert result.reuse_recent_tool_turns is False
    assert result.interactions[0].id == "int_clarify_statistics_timeframe"
    assert result.data == {"stage": CLARIFY_STAGE, "operation": "analyze_metrics"}


def test_handle_ai_request_statistics_parses_structured_final_output(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="statistics",
        description="statistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"get_analytics_snapshot": lambda ctx, timeframe="7d": {}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    structured_message = (
        "{"
        "\"summary\":\"Late deliveries increased compared to last week.\","
        "\"blocks\":["
        "{\"type\":\"text\",\"text\":\"Unscheduled orders rose and late deliveries followed.\"},"
        "{\"type\":\"analytics_kpi\",\"metric_name\":\"late_deliveries\",\"value\":18,\"delta\":4,\"confidence_score\":0.71}"
        "],"
        "\"warnings\":[\"Correlation only; causation is not proven.\"],"
        "\"confidence_score\":0.78"
        "}"
    )
    steps = iter([
        PlannerIntentStep(type="intent", operation="analyze_metrics", needs_clarification=False),
        PlannerFinalStep(type="final", message=structured_message),
    ])
    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", lambda *args, **kwargs: next(steps))

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="why are deliveries late",
        prior_turns=[],
        capability_name="statistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.final_message == "Late deliveries increased compared to last week."
    assert result.data["operation"] == "analyze_metrics"
    assert result.data["statistics_output_kind"] == "narrative"
    assert result.data["blocks"][1]["type"] == "analytics_kpi"


def test_handle_ai_request_statistics_accepts_legacy_structured_output(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="statistics",
        description="statistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"get_analytics_snapshot": lambda ctx, timeframe="7d": {}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    legacy_structured_message = (
        "{"
        "\"summary\":\"Late deliveries increased compared to last week.\","
        "\"key_metrics\":[{\"name\":\"late_deliveries\",\"value\":18,\"delta\":4}],"
        "\"insights\":[{\"type\":\"correlation\",\"description\":\"Higher unscheduled share coincides with more late deliveries.\",\"confidence\":0.71}],"
        "\"warnings\":[\"Correlation only; causation is not proven.\"],"
        "\"confidence_score\":0.78"
        "}"
    )
    steps = iter([
        PlannerIntentStep(type="intent", operation="analyze_metrics", needs_clarification=False),
        PlannerFinalStep(type="final", message=legacy_structured_message),
    ])
    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", lambda *args, **kwargs: next(steps))

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="why are deliveries late",
        prior_turns=[],
        capability_name="statistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.data["statistics_output_kind"] == "legacy"
    assert result.data["statistical_output"]["insights"][0]["type"] == "correlation"


def test_handle_ai_request_statistics_applies_fallback_timeframe_to_execution_facts(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.get_next_step",
        lambda *args, **kwargs: PlannerFinalStep(type="final", message="done"),
    )

    ctx = ServiceContext(incoming_data={}, identity={})
    result = handle_ai_request_with_thread(
        ctx=ctx,
        user_input="show performance",
        prior_turns=[],
        provider=_DummyProvider(),
        system_prompt="custom",
        interaction_response_payload={
            "__interaction_response__": "int_clarify_statistics_timeframe",
            "fallback_timeframe": "last_7_days",
        },
    )

    assert result.success is True
    facts = (((ctx.incoming_data or {}).get("_ai_execution") or {}).get("normalized_facts") or {})
    assert facts["statistics_timeframe"] == "7d"
    assert facts["statistics_timeframe_fallback_applied"] is True


def test_handle_ai_request_statistics_normalizes_timeframe_from_interaction_form(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.get_next_step",
        lambda *args, **kwargs: PlannerFinalStep(type="final", message="done"),
    )

    ctx = ServiceContext(incoming_data={}, identity={})
    result = handle_ai_request_with_thread(
        ctx=ctx,
        user_input="show performance",
        prior_turns=[],
        provider=_DummyProvider(),
        system_prompt="custom",
        interaction_response_payload={
            "__interaction_response__": "int_clarify_statistics_timeframe",
            "interaction_form": {"timeframe": "30d"},
            "fallback_timeframe": "last_7_days",
        },
    )

    assert result.success is True
    facts = (((ctx.incoming_data or {}).get("_ai_execution") or {}).get("normalized_facts") or {})
    assert facts["statistics_timeframe"] == "30d"
    assert "statistics_timeframe_fallback_applied" not in facts


def test_handle_ai_request_statistics_repairs_invalid_structured_final_output(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="statistics",
        description="statistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"get_analytics_snapshot": lambda ctx, timeframe="7d": {}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    invalid_message = "{\"summary\":\"Missing required fields\"}"
    repaired_message = (
        "{"
        "\"summary\":\"Performance stabilized after schedule adherence improved.\","
        "\"blocks\":["
        "{\"type\":\"text\",\"text\":\"Completion rate improved over the selected period.\"},"
        "{\"type\":\"analytics_kpi\",\"metric_name\":\"completion_rate\",\"value\":0.87,\"delta\":0.06,\"confidence_score\":0.74}"
        "],"
        "\"warnings\":[\"Dataset includes partial-day effects.\"],"
        "\"confidence_score\":0.79"
        "}"
    )
    steps = iter([
        PlannerIntentStep(type="intent", operation="analyze_metrics", needs_clarification=False),
        PlannerFinalStep(type="final", message=invalid_message),
        PlannerFinalStep(type="final", message=repaired_message),
    ])
    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", lambda *args, **kwargs: next(steps))

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="show analytics trends",
        prior_turns=[],
        capability_name="statistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.final_message == "Performance stabilized after schedule adherence improved."
    assert result.data["statistical_output_repair_applied"] is True
    assert result.data["statistics_output_kind"] == "narrative"
    assert result.data["blocks"][1]["metric_name"] == "completion_rate"


def test_handle_ai_request_statistics_returns_validation_details_when_repair_fails(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="statistics",
        description="statistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"get_analytics_snapshot": lambda ctx, timeframe="7d": {}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    invalid_message = "{\"summary\":\"Missing required fields\"}"
    steps = iter([
        PlannerIntentStep(type="intent", operation="analyze_metrics", needs_clarification=False),
        PlannerFinalStep(type="final", message=invalid_message),
        PlannerFinalStep(type="final", message=invalid_message),
    ])
    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", lambda *args, **kwargs: next(steps))

    result = handle_ai_request_with_thread(
        ctx=None,
        user_input="show analytics trends",
        prior_turns=[],
        capability_name="statistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is False
    assert result.final_message == "Could not produce a valid statistical output payload."
    assert "statistical_output_validation" in (result.data or {})
    validation = result.data["statistical_output_validation"]
    assert isinstance(validation.get("errors"), list)
    assert any("confidence_score" in error.get("loc", ()) for error in validation["errors"])


def test_handle_ai_request_logistics_retries_when_final_has_no_tool_calls_for_retrieval_question(monkeypatch):
    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"list_orders": lambda ctx, scheduled=True: {"count": 16}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    steps = iter([
        PlannerIntentStep(type="intent", operation="other", needs_clarification=False),
        PlannerFinalStep(type="final", message="There are 16 orders scheduled for today across 2 delivery plans."),
        PlannerToolStep(type="tool", tool="list_orders", parameters={"scheduled": True}),
        PlannerFinalStep(type="final", message="There are 16 scheduled orders for today."),
    ])
    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", lambda *args, **kwargs: next(steps))

    result = handle_ai_request_with_thread(
        ctx=ServiceContext(incoming_data={}, identity={}),
        user_input="How many orders are scheduled today?",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.final_message == "There are 16 scheduled orders for today."
    assert result.tool_turns
    assert result.tool_turns[0]["tool"] == "list_orders"


def test_logistics_operation_contract_triggers_repair_with_exact_required_tool(monkeypatch):
    """When intent resolves to list_plans the repair prompt names list_plans specifically."""
    captured_repair_inputs = []

    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {"list_plans": lambda ctx, **kw: {"route_plan": [{"id": 1, "label": "Plan A"}]}}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    steps = iter([
        PlannerIntentStep(type="intent", operation="list_plans", needs_clarification=False),
        PlannerFinalStep(type="final", message="Here are the plans."),   # finalizes without tool call
        PlannerToolStep(type="tool", tool="list_plans", parameters={}),  # repair returns the right tool
        PlannerFinalStep(type="final", message="Found 1 plan."),
    ])

    def _capture_step(user_input, history, provider, system_prompt=None):
        captured_repair_inputs.append(user_input)
        return next(steps)

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _capture_step)

    result = handle_ai_request_with_thread(
        ctx=ServiceContext(incoming_data={}, identity={}),
        user_input="Show me all plans",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.final_message == "Found 1 plan."
    assert result.tool_turns[0]["tool"] == "list_plans"
    # The repair prompt must refer to the exact required tool, not the generic hint
    repair_prompt = captured_repair_inputs[2]  # 0=intent, 1=first execute final, 2=repair
    assert "list_plans" in repair_prompt
    assert "list_orders/list_plans/list_routes" not in repair_prompt


def test_ai_operation_is_stamped_on_ctx_before_execute(monkeypatch):
    """ctx.ai_operation should be set to the resolved intent operation before the execute loop."""
    stamped_operations = []

    prompts = {
        INTENT_STAGE: "intent-prompt",
        CLARIFY_STAGE: "clarify-prompt",
        EXECUTE_STAGE: "execute-prompt",
    }
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={stage: (lambda prompt=prompt, **_kw: prompt) for stage, prompt in prompts.items()},
        tool_registries={EXECUTE_STAGE: {}},
    )

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    steps = iter([
        PlannerIntentStep(type="intent", operation="list_orders", needs_clarification=False),
        PlannerFinalStep(type="final", message="Done."),
    ])

    ctx = ServiceContext(incoming_data={}, identity={})

    def _capture_step(user_input, history, provider, system_prompt=None):
        stamped_operations.append(getattr(ctx, "ai_operation", None))
        return next(steps)

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _capture_step)

    handle_ai_request_with_thread(
        ctx=ctx,
        user_input="show me orders",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    # First call is intent stage (no operation stamped yet), second is execute stage (stamped)
    assert stamped_operations[0] is None         # intent stage — not yet set
    assert stamped_operations[1] == "list_orders" # execute stage — set by orchestrator


def test_operation_allowlist_blocks_forbidden_tool(monkeypatch):
    """A tool not in the per-operation allowlist should raise ValueError."""
    from Delivery_app_BK.ai.tool_executor import execute_tool, TOOLS

    ctx = ServiceContext(incoming_data={"_ai_route": {"capability_name": "logistics"}}, identity={})
    ctx.ai_operation = "list_orders"

    # assign_orders_to_plan is NOT in the list_orders allowlist
    forbidden_tool = "assign_orders_to_plan"
    dummy_tools = {forbidden_tool: lambda ctx, **kw: {}}

    import pytest
    with pytest.raises(ValueError, match="not permitted for operation 'list_orders'"):
        execute_tool(ctx, forbidden_tool, {}, allowed_tools=dummy_tools)


def test_operation_allowlist_permits_prerequisite_reads_for_mutation(monkeypatch):
    """create_plan may call list_orders (a prerequisite read) before writing."""
    ctx = ServiceContext(incoming_data={}, identity={})
    ctx.ai_operation = "create_plan"

    called = []
    dummy_tools = {"list_orders": lambda ctx, **kw: (called.append("list_orders"), {"order": []})[1]}

    from Delivery_app_BK.ai.tool_executor import execute_tool
    result = execute_tool(ctx, "list_orders", {}, allowed_tools=dummy_tools)

    assert called == ["list_orders"]
    assert "order" in result


# ---------------------------------------------------------------------------
# Analytics chaining helpers
# ---------------------------------------------------------------------------

def test_normalize_insight_depth_passes_through_valid_values():
    from Delivery_app_BK.ai.orchestrator import _normalize_insight_depth

    assert _normalize_insight_depth("risk_brief") == "risk_brief"
    assert _normalize_insight_depth("diagnostic") == "diagnostic"
    assert _normalize_insight_depth("none") == "none"


def test_normalize_insight_depth_returns_none_for_unknown_value():
    from Delivery_app_BK.ai.orchestrator import _normalize_insight_depth

    assert _normalize_insight_depth("full") == "none"
    assert _normalize_insight_depth(None) == "none"
    assert _normalize_insight_depth("") == "none"
    assert _normalize_insight_depth("  RISK_BRIEF  ") == "risk_brief"  # trimmed + lowercased


def test_has_retrieval_entities_returns_true_for_order_list():
    from Delivery_app_BK.ai.orchestrator import _has_retrieval_entities

    turns = [
        {"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}]}}
    ]
    assert _has_retrieval_entities(turns) is True


def test_has_retrieval_entities_returns_false_for_empty_order_list():
    from Delivery_app_BK.ai.orchestrator import _has_retrieval_entities

    turns = [
        {"tool": "list_orders", "params": {}, "result": {"order": [], "count": 0}}
    ]
    assert _has_retrieval_entities(turns) is False


def test_has_retrieval_entities_returns_true_for_plan_list():
    from Delivery_app_BK.ai.orchestrator import _has_retrieval_entities

    turns = [
        {"tool": "list_plans", "params": {}, "result": {"route_plan": [{"id": 5}]}}
    ]
    assert _has_retrieval_entities(turns) is True


def test_has_retrieval_entities_returns_true_based_on_count_field():
    from Delivery_app_BK.ai.orchestrator import _has_retrieval_entities

    turns = [
        {"tool": "list_orders", "params": {}, "result": {"order": [], "count": 3}}
    ]
    assert _has_retrieval_entities(turns) is True


def test_infer_analytics_timeframe_returns_24h_for_today():
    from Delivery_app_BK.ai.orchestrator import _infer_analytics_timeframe

    assert _infer_analytics_timeframe("what orders are scheduled for today?") == "24h"
    assert _infer_analytics_timeframe("show me 24h orders") == "24h"


def test_infer_analytics_timeframe_returns_30d_for_month():
    from Delivery_app_BK.ai.orchestrator import _infer_analytics_timeframe

    assert _infer_analytics_timeframe("orders this month") == "30d"
    assert _infer_analytics_timeframe("last 30 days") == "30d"


def test_infer_analytics_timeframe_defaults_to_7d():
    from Delivery_app_BK.ai.orchestrator import _infer_analytics_timeframe

    assert _infer_analytics_timeframe("show me all orders") == "7d"
    assert _infer_analytics_timeframe("") == "7d"


def test_should_chain_logistics_analytics_returns_false_for_non_logistics(monkeypatch):
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=True,
        final_message="ok",
        tool_turns=[{"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}]}}],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="statistics",
        operation="list_orders",
        insight_depth="risk_brief",
        result=result,
    ) is False


def test_should_chain_logistics_analytics_returns_false_when_depth_is_none(monkeypatch):
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=True,
        final_message="ok",
        tool_turns=[{"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}]}}],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="logistics",
        operation="list_orders",
        insight_depth="none",
        result=result,
    ) is False


def test_should_chain_logistics_analytics_returns_false_for_mutation_operation():
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=True,
        final_message="ok",
        tool_turns=[{"tool": "create_plan", "params": {}, "result": {"id": 99}}],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="logistics",
        operation="create_plan",
        insight_depth="risk_brief",
        result=result,
    ) is False


def test_should_chain_logistics_analytics_returns_false_when_snapshot_already_present():
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=True,
        final_message="ok",
        tool_turns=[
            {"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}]}},
            {"tool": "get_analytics_snapshot", "params": {}, "result": {"metrics": {}}},
        ],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="logistics",
        operation="list_orders",
        insight_depth="risk_brief",
        result=result,
    ) is False


def test_should_chain_logistics_analytics_returns_false_when_result_failed():
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=False,
        final_message="error",
        tool_turns=[{"tool": "list_orders", "params": {}, "result": {"error": "db error"}}],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="logistics",
        operation="list_orders",
        insight_depth="risk_brief",
        result=result,
    ) is False


def test_should_chain_logistics_analytics_returns_false_when_retrieval_empty():
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=True,
        final_message="No orders found.",
        tool_turns=[{"tool": "list_orders", "params": {}, "result": {"order": [], "count": 0}}],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="logistics",
        operation="list_orders",
        insight_depth="risk_brief",
        result=result,
    ) is False


def test_should_chain_logistics_analytics_returns_true_when_all_conditions_met():
    from Delivery_app_BK.ai.orchestrator import _should_chain_logistics_analytics, OrchestratorResult

    result = OrchestratorResult(
        success=True,
        final_message="Here are today's orders.",
        tool_turns=[{"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}, {"id": 2}]}}],
        data={},
    )
    assert _should_chain_logistics_analytics(
        capability_name="logistics",
        operation="list_orders",
        insight_depth="risk_brief",
        result=result,
    ) is True


def test_append_logistics_analytics_snapshot_adds_turn_and_metadata(monkeypatch):
    from Delivery_app_BK.ai.orchestrator import _append_logistics_analytics_snapshot, OrchestratorResult

    fake_analytics = {"metrics": {"total_orders": 20, "failed_orders": 2, "completion_rate": 0.80}}

    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.execute_tool",
        lambda ctx, tool_name, params, allowed_tools=None: fake_analytics,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.get_capability_profile",
        lambda name: type("Cap", (), {"get_tools": lambda self, stage: {}})(),
    )

    result = OrchestratorResult(
        success=True,
        final_message="orders listed",
        tool_turns=[{"tool": "list_orders", "params": {}, "result": {"order": [{"id": 1}]}}],
        data={},
    )
    ctx = ServiceContext(incoming_data={}, identity={})

    _append_logistics_analytics_snapshot(
        ctx=ctx,
        user_input="show me today's orders",
        result=result,
        insight_depth="risk_brief",
    )

    analytics_turns = [t for t in result.tool_turns if t["tool"] == "get_analytics_snapshot"]
    assert len(analytics_turns) == 1
    assert analytics_turns[0]["result"] == fake_analytics
    assert analytics_turns[0]["params"]["timeframe"] == "24h"
    assert result.data["insight_depth"] == "risk_brief"
    assert result.data["analytics_timeframe"] == "24h"
