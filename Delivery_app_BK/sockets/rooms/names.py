def build_user_room(user_id: int | str) -> str:
    return f"user:{user_id}"


def build_user_app_room(user_id: int | str, app_scope: str) -> str:
    return f"user:{user_id}:{app_scope}"


def build_team_orders_room(team_id: int | str) -> str:
    return f"team:{team_id}:orders"


def build_team_order_cases_room(team_id: int | str) -> str:
    return f"team:{team_id}:order_cases"


def build_team_admin_room(team_id: int | str) -> str:
    return f"team:{team_id}:admin"


def build_route_orders_room(team_id: int | str, route_id: int | str) -> str:
    return f"team:{team_id}:route:{route_id}:orders"


def build_team_driver_live_room(team_id: int | str) -> str:
    return f"team:{team_id}:drivers_live"


def build_order_chat_room(team_id: int | str, order_id: int | str) -> str:
    return f"team:{team_id}:order_chat:{order_id}"


def build_external_form_room(team_id: int | str, user_id: int | str) -> str:
    return f"external_form:{team_id}:{user_id}"


def build_team_members_room(team_id: int | str) -> str:
    return f"team:{team_id}:members"
