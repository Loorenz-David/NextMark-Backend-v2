from importlib import import_module

from Delivery_app_BK.routers.utils.role_decorator import install_blueprint_scope_guard


def __getattr__(name: str):
    if name == "ai":
        return import_module("Delivery_app_BK.routers.api_v2.ai")
    raise AttributeError(name)


def _load_blueprints():
    from .ai import ai_bp
    from .auth import auth_bp
    from .bootstrap import bootstrap_bp
    from .client_form import client_form_bp, public_client_form_bp
    from .costumer import costumer_bp
    from .route_plan.local_delivery_plans import route_groups_bp as local_delivery_plans_bp
    from .route_plan.plan import route_plans_bp as plan_bp
    from .route_plan.plan_overviews import route_plan_overviews_bp as plan_overviews_bp
    from .route_plan.route_operations import route_operations_bp
    from .drivers import drivers_bp
    from .external_integration import external_integration_bp
    from .infrastructure import infrastructure_bp
    from .integration_email import email_bp
    from .integration_shopify import shopify_bp
    from .integration_twilio import twilio_bp
    from .integrations import integrations_bp
    from .item import item_bp
    from .item_position import item_position_bp
    from .item_property import item_property_bp
    from .item_state import item_state_bp
    from .item_type import item_type_bp
    from .label_template import label_template_bp
    from .message_template import message_template_bp
    from .order import order_bp
    from .order_assignment import order_assignment_bp
    from .order_case import order_case_bp
    from .order_tracking import public_order_tracking_bp
    from .seed import seed_bp
    from .team_invitation import team_invitation_bp
    from .team_members import team_bp
    from .user import user_bp
    from .user_registration import user_registration_bp
    from .user_role import user_role_bp
    from .user_role_rule import user_role_rule_bp
    from .zones import zone_bp
    from .notifications import notifications_bp

    admin_blueprints = [
        item_bp,
        item_type_bp,
        item_property_bp,
        item_position_bp,
        item_state_bp,
        label_template_bp,
        message_template_bp,
        plan_bp,
        local_delivery_plans_bp,
        order_bp,
        order_assignment_bp,
        infrastructure_bp,
        external_integration_bp,
        user_role_bp,
        user_role_rule_bp,
        user_bp,
        team_bp,
        team_invitation_bp,
        seed_bp,
        bootstrap_bp,
        shopify_bp,
        integrations_bp,
        twilio_bp,
        email_bp,
        route_operations_bp,
        plan_overviews_bp,
        costumer_bp,
        client_form_bp,
        ai_bp,
        zone_bp,
        notifications_bp,
    ]

    return {
        "admin_blueprints": admin_blueprints,
        "order_case_bp": order_case_bp,
        "drivers_bp": drivers_bp,
        "public_client_form_bp": public_client_form_bp,
        "public_order_tracking_bp": public_order_tracking_bp,
        "all": {
            "item_bp": item_bp,
            "item_type_bp": item_type_bp,
            "item_property_bp": item_property_bp,
            "item_position_bp": item_position_bp,
            "item_state_bp": item_state_bp,
            "local_delivery_plans_bp": local_delivery_plans_bp,
            "label_template_bp": label_template_bp,
            "message_template_bp": message_template_bp,
            "plan_bp": plan_bp,
            "order_bp": order_bp,
            "order_assignment_bp": order_assignment_bp,
            "infrastructure_bp": infrastructure_bp,
            "external_integration_bp": external_integration_bp,
            "order_case_bp": order_case_bp,
            "user_role_bp": user_role_bp,
            "user_role_rule_bp": user_role_rule_bp,
            "user_bp": user_bp,
            "user_registration_bp": user_registration_bp,
            "team_bp": team_bp,
            "team_invitation_bp": team_invitation_bp,
            "auth_bp": auth_bp,
            "seed_bp": seed_bp,
            "bootstrap_bp": bootstrap_bp,
            "shopify_bp": shopify_bp,
            "integrations_bp": integrations_bp,
            "twilio_bp": twilio_bp,
            "email_bp": email_bp,
            "route_operations_bp": route_operations_bp,
            "plan_overviews_bp": plan_overviews_bp,
            "costumer_bp": costumer_bp,
            "drivers_bp": drivers_bp,
            "client_form_bp": client_form_bp,
            "ai_bp": ai_bp,
            "zone_bp": zone_bp,
            "notifications_bp": notifications_bp,
            "public_client_form_bp": public_client_form_bp,
            "public_order_tracking_bp": public_order_tracking_bp,
        },
    }


def _install_scope_guards(blueprints):
    for blueprint in blueprints["admin_blueprints"]:
        install_blueprint_scope_guard(blueprint, "admin")
    install_blueprint_scope_guard(blueprints["order_case_bp"], ("admin", "driver"))
    install_blueprint_scope_guard(blueprints["drivers_bp"], "driver")


def register_v2_blueprints(app):
    blueprints = _load_blueprints()
    _install_scope_guards(blueprints)
    bp = blueprints["all"]
    app.register_blueprint(bp["item_bp"], url_prefix="/api_v2/items")
    app.register_blueprint(bp["item_type_bp"], url_prefix="/api_v2/item_types")
    app.register_blueprint(bp["item_property_bp"], url_prefix="/api_v2/item_properties")
    app.register_blueprint(bp["item_position_bp"], url_prefix="/api_v2/item_positions")
    app.register_blueprint(bp["item_state_bp"], url_prefix="/api_v2/item_states")
    app.register_blueprint(bp["local_delivery_plans_bp"], url_prefix="/api_v2/local_delivery_plans")
    app.register_blueprint(bp["label_template_bp"], url_prefix="/api_v2/label_templates")
    app.register_blueprint(bp["message_template_bp"], url_prefix="/api_v2/message_templates")
    app.register_blueprint(bp["plan_bp"], url_prefix="/api_v2/route_plans")
    app.register_blueprint(bp["order_bp"], url_prefix="/api_v2/orders")
    app.register_blueprint(bp["order_assignment_bp"], url_prefix="/api_v2/order_assignments")
    app.register_blueprint(bp["infrastructure_bp"], url_prefix="/api_v2/infrastructures")
    app.register_blueprint(bp["external_integration_bp"], url_prefix="/api_v2/external_integrations")
    app.register_blueprint(bp["order_case_bp"], url_prefix="/api_v2/order_cases")
    app.register_blueprint(bp["user_role_bp"], url_prefix="/api_v2/user_roles")
    app.register_blueprint(bp["user_role_rule_bp"], url_prefix="/api_v2/user_role_rules")
    app.register_blueprint(bp["user_bp"], url_prefix="/api_v2/users")
    app.register_blueprint(bp["user_registration_bp"], url_prefix="/api_v2/user_registration")
    app.register_blueprint(bp["team_bp"], url_prefix="/api_v2/teams")
    app.register_blueprint(bp["team_invitation_bp"], url_prefix="/api_v2/team_invitations")
    app.register_blueprint(bp["auth_bp"], url_prefix="/api_v2/auths")
    app.register_blueprint(bp["seed_bp"], url_prefix="/api_v2/seed")
    app.register_blueprint(bp["bootstrap_bp"], url_prefix="/api_v2/bootstrap")
    app.register_blueprint(bp["shopify_bp"], url_prefix="/api_v2/shopify")
    app.register_blueprint(bp["integrations_bp"], url_prefix="/api_v2/integrations")
    app.register_blueprint(bp["twilio_bp"], url_prefix="/api_v2/twilio")
    app.register_blueprint(bp["email_bp"], url_prefix="/api_v2/email")
    app.register_blueprint(bp["route_operations_bp"], url_prefix="/api_v2/route_operations")
    app.register_blueprint(bp["plan_overviews_bp"], url_prefix="/api_v2/route_plan_overviews")
    app.register_blueprint(bp["costumer_bp"], url_prefix="/api_v2/costumers")
    app.register_blueprint(bp["drivers_bp"], url_prefix="/api_v2/drivers")
    app.register_blueprint(bp["client_form_bp"], url_prefix="/api_v2")
    app.register_blueprint(bp["public_client_form_bp"], url_prefix="/api_v2")
    app.register_blueprint(bp["public_order_tracking_bp"], url_prefix="/api_v2")
    app.register_blueprint(bp["ai_bp"], url_prefix="/api_v2/ai")
    app.register_blueprint(bp["zone_bp"], url_prefix="/api_v2/zones")
    app.register_blueprint(bp["notifications_bp"], url_prefix="/api_v2/notifications")
