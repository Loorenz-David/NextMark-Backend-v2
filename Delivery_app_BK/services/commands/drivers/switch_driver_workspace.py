from Delivery_app_BK.services.commands.user.switch_user_workspace import switch_user_workspace
from Delivery_app_BK.services.context import ServiceContext


def switch_driver_workspace(ctx: ServiceContext):
    return switch_user_workspace(ctx)
