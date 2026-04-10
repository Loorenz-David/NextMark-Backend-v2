from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast


INTENT_STAGE = "intent"
CLARIFY_STAGE = "clarify"
EXECUTE_STAGE = "execute"

StageName = Literal["intent", "clarify", "execute"]
ALL_STAGE_NAMES: tuple[StageName, ...] = (
    INTENT_STAGE,
    CLARIFY_STAGE,
    EXECUTE_STAGE,
)


@dataclass(frozen=True)
class StageDefinition:
    name: StageName
    description: str
    allows_tools: bool = False


STAGE_DEFINITIONS: dict[StageName, StageDefinition] = {
    INTENT_STAGE: StageDefinition(
        name=INTENT_STAGE,
        description="Route the request to the correct capability and operation.",
        allows_tools=False,
    ),
    CLARIFY_STAGE: StageDefinition(
        name=CLARIFY_STAGE,
        description="Identify missing or ambiguous information and ask for it.",
        allows_tools=False,
    ),
    EXECUTE_STAGE: StageDefinition(
        name=EXECUTE_STAGE,
        description="Execute the scoped domain workflow with the selected tool set.",
        allows_tools=True,
    ),
}


def validate_stage_name(stage_name: str) -> StageName:
    if stage_name not in STAGE_DEFINITIONS:
        raise ValueError(
            f"Unknown AI stage '{stage_name}'. Allowed: {list(STAGE_DEFINITIONS.keys())}"
        )
    return cast(StageName, stage_name)