from dataclasses import dataclass, field
from collections.abc import Callable


@dataclass
class PlanObjectiveCreateResult:
    instances: list[object] = field(default_factory=list)
    post_flush_actions: list[Callable[[], None]] = field(default_factory=list)
    bundle_serializer: Callable[[], dict] | None = None

    def serialize_bundle(self) -> dict:
        if not self.bundle_serializer:
            return {}
        return self.bundle_serializer()
