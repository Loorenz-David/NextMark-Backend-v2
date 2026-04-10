from Delivery_app_BK.ai.capabilities.base import CapabilityProfile
from Delivery_app_BK.ai.orchestrator import handle_ai_request_with_thread
from Delivery_app_BK.ai.schemas import PlannerFinalStep, PlannerIntentStep
from Delivery_app_BK.ai.stages import CLARIFY_STAGE, EXECUTE_STAGE, INTENT_STAGE
from Delivery_app_BK.ai.tools.analytics_tools import get_analytics_snapshot
from Delivery_app_BK.services.context import ServiceContext


class _DummyProvider:
    name = "dummy"


def test_regression_matrix_timeout_surfaces_structured_failure(monkeypatch):
    def _raise_timeout(*_args, **_kwargs):
        raise TimeoutError("llm request timed out")

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_next_step", _raise_timeout)

    result = handle_ai_request_with_thread(
        ctx=ServiceContext(incoming_data={}, identity={}),
        user_input="show performance",
        prior_turns=[],
        provider=_DummyProvider(),
        system_prompt="custom",
        capability_name="statistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is False
    assert "timed out" in result.final_message
    assert (result.data or {}).get("stage") == EXECUTE_STAGE


def test_regression_matrix_partial_data_marks_snapshot_incomplete(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.analytics_tools.get_metrics",
        lambda ctx, timeframe: {
            "total_orders": 42,
            "data_status": {"is_complete": True, "pages_fetched": 1},
        },
    )
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.analytics_tools.get_trends",
        lambda ctx, timeframe: {
            "items": [{"date": "2026-03-22", "orders_created": 4}],
            "data_status": {"is_complete": False, "warning": "truncated trends"},
        },
    )
    monkeypatch.setattr(
        "Delivery_app_BK.ai.tools.analytics_tools.get_breakdowns",
        lambda ctx, timeframe: {
            "items": [{"dimension": "scheduled_status", "values": []}],
            "data_status": {"is_complete": True, "pages_fetched": 1},
        },
    )

    snapshot = get_analytics_snapshot(ServiceContext(incoming_data={}, identity={}), "7d")

    assert snapshot["data_status"]["is_complete"] is False
    assert snapshot["data_status"]["warnings"] == ["truncated trends"]


def test_regression_matrix_malformed_model_output_returns_validation_details(monkeypatch):
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

    monkeypatch.setattr("Delivery_app_BK.ai.orchestrator.get_capability_profile", lambda _name: capability)
    monkeypatch.setattr(
        "Delivery_app_BK.ai.orchestrator.select_provider_for_stage",
        lambda capability_name, stage_name: _DummyProvider(),
    )

    malformed = "not-json-at-all"
    steps = iter([
        PlannerIntentStep(type="intent", operation="analyze_metrics", needs_clarification=False),
        PlannerFinalStep(type="final", message=malformed),
        PlannerFinalStep(type="final", message=malformed),
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
    validation = (result.data or {}).get("statistical_output_validation") or {}
    assert isinstance(validation.get("errors"), list)
    assert validation.get("raw_error")
