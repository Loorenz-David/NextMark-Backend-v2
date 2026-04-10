from __future__ import annotations

from Delivery_app_BK.ai.capabilities.base import CapabilityProfile, ModelTarget
from Delivery_app_BK.ai.prompts.user_config_clarify_prompt import build_user_config_clarify_prompt
from Delivery_app_BK.ai.prompts.user_config_execute_prompt import build_user_config_execute_prompt
from Delivery_app_BK.ai.prompts.user_config_intent_prompt import build_user_config_intent_prompt
from Delivery_app_BK.ai.stages import CLARIFY_STAGE, EXECUTE_STAGE, INTENT_STAGE
from Delivery_app_BK.ai.tools.user_config_tools import (
    apply_item_taxonomy_proposal_tool,
    create_item_taxonomy_proposal_tool,
    create_item_property_config_tool,
    create_item_type_config_tool,
    get_item_property_config_tool,
    get_item_type_config_tool,
    link_properties_to_item_type_tool,
    list_item_properties_config_tool,
    list_item_types_config_tool,
    update_item_property_config_tool,
    update_item_type_config_tool,
)


USER_CONFIG_TOOLS = {
    "list_item_types_config": list_item_types_config_tool,
    "list_item_properties_config": list_item_properties_config_tool,
    "get_item_type_config": get_item_type_config_tool,
    "get_item_property_config": get_item_property_config_tool,
    "create_item_type_config": create_item_type_config_tool,
    "create_item_property_config": create_item_property_config_tool,
    "update_item_type_config": update_item_type_config_tool,
    "update_item_property_config": update_item_property_config_tool,
    "link_properties_to_item_type": link_properties_to_item_type_tool,
    "create_item_taxonomy_proposal": create_item_taxonomy_proposal_tool,
    "apply_item_taxonomy_proposal": apply_item_taxonomy_proposal_tool,
}


USER_CONFIG_CAPABILITY = CapabilityProfile(
    name="user_config",
    description="User application configuration and preferences.",
    prompt_builders={
        INTENT_STAGE: build_user_config_intent_prompt,
        CLARIFY_STAGE: build_user_config_clarify_prompt,
        EXECUTE_STAGE: build_user_config_execute_prompt,
    },
    tool_registries={
        INTENT_STAGE: {},
        CLARIFY_STAGE: {},
        EXECUTE_STAGE: USER_CONFIG_TOOLS,
    },
    stage_models={
        INTENT_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
        CLARIFY_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
        EXECUTE_STAGE: ModelTarget(provider_name="openai", model_name="gpt-4.1-mini"),
    },
    default_stage=EXECUTE_STAGE,
)