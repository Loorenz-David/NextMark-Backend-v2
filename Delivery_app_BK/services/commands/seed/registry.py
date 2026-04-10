from dataclasses import dataclass, field
from typing import Callable, Iterable

from .seeders import (
    seed_base_roles,
    seed_user_roles,
    seed_plan_states,
    seed_order_states,
    seed_item_states,
)


@dataclass(frozen=True)
class SeedDefinition:
    name: str
    seeder: Callable
    depends_on: Iterable[str] = field(default_factory=tuple)


SEED_REGISTRY = [
    SeedDefinition(
        name="base_roles",
        seeder=seed_base_roles,
        depends_on=(),
    ),
    SeedDefinition(
        name="user_roles",
        seeder=seed_user_roles,
        depends_on=("base_roles",),
    ),
    SeedDefinition(
        name="plan_states",
        seeder=seed_plan_states,
        depends_on=(),
    ),
    SeedDefinition(
        name="order_states",
        seeder=seed_order_states,
        depends_on=(),
    ),
    SeedDefinition(
        name="item_states",
        seeder=seed_item_states,
        depends_on=(),
    ),
]
