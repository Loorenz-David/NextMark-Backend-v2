from Delivery_app_BK.errors import NotFound, PermissionDenied, ValidationFailed
from Delivery_app_BK.models import User, db
from Delivery_app_BK.services.commands.auth.token_utils import build_user_tokens
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.user import (
    ensure_app_workspace_state,
    parse_workspace_kind,
    set_app_current_workspace,
)


def switch_user_workspace(ctx: ServiceContext):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to switch workspace.")
    if not ctx.app_scope:
        raise ValidationFailed("app_scope is required to switch workspace.")

    target_workspace = parse_workspace_kind((ctx.incoming_data or {}).get("target_workspace"))

    user = db.session.get(User, ctx.user_id)
    if not user:
        raise NotFound("User was not found.")
    current_context = ensure_app_workspace_state(user, ctx.app_scope)

    if current_context["current_workspace"] == target_workspace:
        tokens = build_user_tokens(
            user,
            app_scope=ctx.app_scope,
            session_scope_id=ctx.session_scope_id,
            time_zone=ctx.time_zone,
        )
        db.session.commit()
        db.session.refresh(user)
        return tokens

    if target_workspace == "team":
        if not current_context["has_team_workspace"]:
            raise ValidationFailed("No team workspace is available for this user.")

        set_app_current_workspace(user, ctx.app_scope, "team")
        next_context = ensure_app_workspace_state(user, ctx.app_scope)
        if next_context["current_workspace"] != "team":
            raise PermissionDenied("Current team workspace cannot access this app.")
    else:
        set_app_current_workspace(user, ctx.app_scope, "personal")
        ensure_app_workspace_state(user, ctx.app_scope)

    db.session.commit()
    db.session.refresh(user)

    return build_user_tokens(
        user,
        app_scope=ctx.app_scope,
        session_scope_id=ctx.session_scope_id,
        time_zone=ctx.time_zone,
    )
