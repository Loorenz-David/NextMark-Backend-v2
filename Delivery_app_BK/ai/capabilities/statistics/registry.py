from __future__ import annotations

from Delivery_app_BK.ai.capabilities.base import CapabilityProfile, ModelTarget
from Delivery_app_BK.ai.prompts.statistics_clarify_prompt import build_statistics_clarify_prompt
from Delivery_app_BK.ai.prompts.statistics_execute_prompt import build_statistics_execute_prompt
from Delivery_app_BK.ai.prompts.statistics_intent_prompt import build_statistics_intent_prompt
from Delivery_app_BK.ai.stages import CLARIFY_STAGE, EXECUTE_STAGE, INTENT_STAGE
from Delivery_app_BK.ai.tools.analytics_tools import (
    get_analytics_snapshot,
    get_daily_summary,
    get_route_metrics_tool,
)


STATISTICS_TOOLS = {
    "get_analytics_snapshot": get_analytics_snapshot,
    "get_daily_summary": get_daily_summary,
    "get_route_metrics_tool": get_route_metrics_tool,
}


STATISTICS_CAPABILITY = CapabilityProfile(
    name="statistics",
    description="Read-only logistics analytics and statistical interpretation.",
    prompt_builders={
        INTENT_STAGE: build_statistics_intent_prompt,
        CLARIFY_STAGE: build_statistics_clarify_prompt,
        EXECUTE_STAGE: build_statistics_execute_prompt,
    },
    tool_registries={
        INTENT_STAGE: {},
        CLARIFY_STAGE: {},
        EXECUTE_STAGE: STATISTICS_TOOLS,
    },
    stage_models={
        INTENT_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
        CLARIFY_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
        EXECUTE_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
    },
    default_stage=EXECUTE_STAGE,
)
