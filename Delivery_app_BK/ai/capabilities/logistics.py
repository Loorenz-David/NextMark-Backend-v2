from __future__ import annotations

from Delivery_app_BK.ai.capabilities.base import CapabilityProfile, ModelTarget
from Delivery_app_BK.ai.prompts.logistics_clarify_prompt import build_logistics_clarify_prompt
from Delivery_app_BK.ai.prompts.logistics_execute_prompt import build_logistics_execute_prompt
from Delivery_app_BK.ai.prompts.logistics_intent_prompt import build_logistics_intent_prompt
from Delivery_app_BK.ai.stages import CLARIFY_STAGE, EXECUTE_STAGE, INTENT_STAGE
from Delivery_app_BK.ai.tool_registry import TOOLS


LOGISTICS_CAPABILITY = CapabilityProfile(
    name="logistics",
    description="Delivery, plan, route, item, and order operations.",
    prompt_builders={
        INTENT_STAGE: build_logistics_intent_prompt,
        CLARIFY_STAGE: build_logistics_clarify_prompt,
        EXECUTE_STAGE: build_logistics_execute_prompt,
    },
    tool_registries={
        INTENT_STAGE: {},
        CLARIFY_STAGE: {},
        EXECUTE_STAGE: TOOLS,
    },
    stage_models={
        INTENT_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
        CLARIFY_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
        EXECUTE_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
    },
    default_stage=EXECUTE_STAGE,
)