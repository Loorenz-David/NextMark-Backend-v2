"""Plan type dispatch.

Shared order code hands plan-type work to the module registered for the plan's
type and never inspects what a plan type does. Each type's behaviour lives in
its own `commands/<type>_app/` package and is bound to the contract here.

See docs/architecture/plan-types.md.
"""

from .contract import PlanTypeModule
from .registry import get_plan_type_module

__all__ = [
    "PlanTypeModule",
    "get_plan_type_module",
]
