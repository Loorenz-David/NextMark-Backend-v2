from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from Delivery_app_BK.ai.stages import EXECUTE_STAGE, StageName, validate_stage_name


PromptBuilder = Callable[..., str]
ToolRegistry = Mapping[str, Callable[..., dict[str, Any]]]


@dataclass(frozen=True)
class ModelTarget:
    provider_name: str = "openai"
    model_name: str = "gpt-4.1-mini"


@dataclass(frozen=True)
class CapabilityProfile:
    name: str
    description: str
    prompt_builders: Mapping[StageName, PromptBuilder]
    tool_registries: Mapping[StageName, ToolRegistry] = field(default_factory=dict)
    stage_models: Mapping[StageName, ModelTarget] = field(default_factory=dict)
    default_stage: StageName = EXECUTE_STAGE

    def build_prompt(self, stage_name: str, **kwargs) -> str:
        validated_stage = validate_stage_name(stage_name)
        try:
            builder = self.prompt_builders[validated_stage]
        except KeyError as exc:
            raise ValueError(
                f"Capability '{self.name}' does not define a prompt for stage '{validated_stage}'."
            ) from exc
        return builder(**kwargs)

    def get_tools(self, stage_name: str) -> ToolRegistry:
        validated_stage = validate_stage_name(stage_name)
        return self.tool_registries.get(validated_stage, {})

    def get_model_target(self, stage_name: str) -> ModelTarget:
        validated_stage = validate_stage_name(stage_name)
        return self.stage_models.get(validated_stage, ModelTarget())