from ...context import ServiceContext
from .runner import run_seed_registry


def seed_initial_data(ctx: ServiceContext):
    ctx.inject_team_id = False
    run_seed_registry(ctx)
    return {}
