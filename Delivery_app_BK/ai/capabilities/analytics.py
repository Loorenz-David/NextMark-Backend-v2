from __future__ import annotations

from Delivery_app_BK.ai.capabilities.base import CapabilityProfile, ModelTarget
from Delivery_app_BK.ai.prompts.analytics_execute_prompt import build_analytics_execute_prompt
from Delivery_app_BK.ai.stages import EXECUTE_STAGE
from Delivery_app_BK.ai.tools.analytics_tools import (
    get_analytics_snapshot,
    get_daily_summary,
    get_route_metrics_tool,
    get_zone_metrics,
    get_zone_trends,
)


ANALYTICS_TOOLS = {
    "get_daily_summary": get_daily_summary,
    "get_route_metrics_tool": get_route_metrics_tool,
    "get_analytics_snapshot": get_analytics_snapshot,
    "get_zone_metrics": get_zone_metrics,
    "get_zone_trends": get_zone_trends,
}


ANALYTICS_CAPABILITY = CapabilityProfile(
    name="analytics",
    description="Grounded operational analytics over route and daily fact tables.",
    prompt_builders={
        EXECUTE_STAGE: build_analytics_execute_prompt,
    },
    tool_registries={
        EXECUTE_STAGE: ANALYTICS_TOOLS,
    },
    stage_models={
        EXECUTE_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
    },
    default_stage=EXECUTE_STAGE,
)
