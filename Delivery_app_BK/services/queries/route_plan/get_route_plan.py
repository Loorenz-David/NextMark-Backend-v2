from Delivery_app_BK.services.queries.route_plan.get_plan import get_plan


def get_route_plan(plan_id, ctx):
    return get_plan(plan_id, ctx)