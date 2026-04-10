from __future__ import annotations

from Delivery_app_BK.ai.capabilities.base import CapabilityProfile
from Delivery_app_BK.ai.capabilities.analytics import ANALYTICS_CAPABILITY
from Delivery_app_BK.ai.capabilities.logistics import LOGISTICS_CAPABILITY
from Delivery_app_BK.ai.capabilities.statistics import STATISTICS_CAPABILITY
from Delivery_app_BK.ai.capabilities.user_config import USER_CONFIG_CAPABILITY


CAPABILITY_REGISTRY: dict[str, CapabilityProfile] = {
    ANALYTICS_CAPABILITY.name: ANALYTICS_CAPABILITY,
    LOGISTICS_CAPABILITY.name: LOGISTICS_CAPABILITY,
    STATISTICS_CAPABILITY.name: STATISTICS_CAPABILITY,
    USER_CONFIG_CAPABILITY.name: USER_CONFIG_CAPABILITY,
}


def get_capability_profile(name: str = "logistics") -> CapabilityProfile:
    try:
        return CAPABILITY_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown AI capability '{name}'. Allowed: {list(CAPABILITY_REGISTRY.keys())}"
        ) from exc