from __future__ import annotations

from collections.abc import Callable
from typing import Any

from Delivery_app_BK.ai.capabilities import get_capability_profile
from Delivery_app_BK.ai.providers.anthropic_provider import AnthropicProvider
from Delivery_app_BK.ai.providers.gemini_provider import GeminiProvider
from Delivery_app_BK.ai.providers.openai_provider import OpenAIProvider


PROVIDER_FACTORIES: dict[str, Callable[[str], Any]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


def create_provider(provider_name: str, model_name: str):
    try:
        factory = PROVIDER_FACTORIES[provider_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown AI provider '{provider_name}'. Allowed: {list(PROVIDER_FACTORIES.keys())}"
        ) from exc
    return factory(model_name)


def select_provider_for_stage(capability_name: str, stage_name: str):
    capability = get_capability_profile(capability_name)
    target = capability.get_model_target(stage_name)
    return create_provider(target.provider_name, target.model_name)