"""Admin routers for the public client-form configuration.

  Settings (singleton per team):
    GET    /api_v2/client_form_config/settings
    PATCH  /api_v2/client_form_config/settings

  Terms & conditions (immutable versions — no PATCH or DELETE):
    GET    /api_v2/client_form_config/terms          → version history, newest first
    PUT    /api_v2/client_form_config/terms          → publish a new version

  Rules (ordered):
    GET / PUT / PATCH / DELETE  /api_v2/client_form_config/rules
    POST                        /api_v2/client_form_config/rules/reorder

  Media (ordered per placement):
    GET / PUT / PATCH / DELETE  /api_v2/client_form_config/media
    POST                        /api_v2/client_form_config/media/reorder

  Post-submit redirect pages (at most one active):
    GET / PUT / PATCH / DELETE  /api_v2/client_form_config/redirects
    POST                        /api_v2/client_form_config/redirects/activate

The public form never calls these — it receives its configuration through the
token-authenticated client-form endpoint in `client_form.py`.
"""

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.routers.utils.role_decorator import ADMIN, ASSISTANT, role_required
from Delivery_app_BK.services.commands.client_form_config.activate_client_form_redirect import (
    activate_client_form_redirect as activate_client_form_redirect_service,
)
from Delivery_app_BK.services.commands.client_form_config.create_client_form_media import (
    create_client_form_media as create_client_form_media_service,
)
from Delivery_app_BK.services.commands.client_form_config.create_client_form_redirect import (
    create_client_form_redirect as create_client_form_redirect_service,
)
from Delivery_app_BK.services.commands.client_form_config.create_client_form_rule import (
    create_client_form_rule as create_client_form_rule_service,
)
from Delivery_app_BK.services.commands.client_form_config.delete_client_form_media import (
    delete_client_form_media as delete_client_form_media_service,
)
from Delivery_app_BK.services.commands.client_form_config.delete_client_form_redirect import (
    delete_client_form_redirect as delete_client_form_redirect_service,
)
from Delivery_app_BK.services.commands.client_form_config.delete_client_form_rule import (
    delete_client_form_rule as delete_client_form_rule_service,
)
from Delivery_app_BK.services.commands.client_form_config.publish_terms_version import (
    publish_terms_version as publish_terms_version_service,
)
from Delivery_app_BK.services.commands.client_form_config.reorder_client_form_media import (
    reorder_client_form_media as reorder_client_form_media_service,
)
from Delivery_app_BK.services.commands.client_form_config.reorder_client_form_rules import (
    reorder_client_form_rules as reorder_client_form_rules_service,
)
from Delivery_app_BK.services.commands.client_form_config.update_client_form_media import (
    update_client_form_media as update_client_form_media_service,
)
from Delivery_app_BK.services.commands.client_form_config.update_client_form_redirect import (
    update_client_form_redirect as update_client_form_redirect_service,
)
from Delivery_app_BK.services.commands.client_form_config.update_client_form_rule import (
    update_client_form_rule as update_client_form_rule_service,
)
from Delivery_app_BK.services.commands.client_form_config.upsert_client_form_settings import (
    upsert_client_form_settings as upsert_client_form_settings_service,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.client_form_config.get_client_form_projection import (
    get_client_form_projection as get_client_form_projection_service,
)
from Delivery_app_BK.services.queries.client_form_config.get_client_form_settings import (
    get_client_form_settings as get_client_form_settings_service,
)
from Delivery_app_BK.services.queries.client_form_config.list_client_form_media import (
    list_client_form_media as list_client_form_media_service,
)
from Delivery_app_BK.services.queries.client_form_config.list_client_form_redirects import (
    list_client_form_redirects as list_client_form_redirects_service,
)
from Delivery_app_BK.services.queries.client_form_config.list_client_form_rules import (
    list_client_form_rules as list_client_form_rules_service,
)
from Delivery_app_BK.services.queries.client_form_config.list_terms_versions import (
    list_terms_versions as list_terms_versions_service,
)
from Delivery_app_BK.services.run_service import run_service


client_form_config_bp = Blueprint("api_v2_client_form_config_bp", __name__)


def _run_query(service_fn):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=request.args.to_dict(),
        identity=identity,
    )
    outcome = run_service(lambda c: service_fn(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)


def _run_command(service_fn, return_data: bool = True):
    identity = get_jwt()
    ctx = ServiceContext(
        incoming_data=request.get_json(silent=True) or {},
        identity=identity,
    )
    outcome = run_service(lambda c: service_fn(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data if return_data else {},
        warnings=ctx.warnings,
    )


# ── Rendered form projection ───────────────────────────────────────────────────

@client_form_config_bp.route("/projection", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_client_form_projection():
    """The configuration as the form renders it, for an authenticated device.

    Same body as the public token route's `config`, built by the same code — the
    in-store device and the emailed link must not be able to disagree about what
    the form contains.
    """
    return _run_query(get_client_form_projection_service)


# ── Settings ───────────────────────────────────────────────────────────────────

@client_form_config_bp.route("/settings", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_client_form_settings():
    return _run_query(get_client_form_settings_service)


@client_form_config_bp.route("/settings", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def upsert_client_form_settings():
    return _run_command(upsert_client_form_settings_service)


# ── Terms & conditions ─────────────────────────────────────────────────────────

@client_form_config_bp.route("/terms", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_terms_versions():
    return _run_query(list_terms_versions_service)


@client_form_config_bp.route("/terms", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def publish_terms_version():
    return _run_command(publish_terms_version_service)


# ── Rules ──────────────────────────────────────────────────────────────────────

@client_form_config_bp.route("/rules", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_client_form_rules():
    return _run_query(list_client_form_rules_service)


@client_form_config_bp.route("/rules", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_client_form_rule():
    return _run_command(create_client_form_rule_service)


@client_form_config_bp.route("/rules", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_client_form_rule():
    return _run_command(update_client_form_rule_service, return_data=False)


@client_form_config_bp.route("/rules", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_client_form_rule():
    return _run_command(delete_client_form_rule_service, return_data=False)


@client_form_config_bp.route("/rules/reorder", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def reorder_client_form_rules():
    return _run_command(reorder_client_form_rules_service)


# ── Media ──────────────────────────────────────────────────────────────────────

@client_form_config_bp.route("/media", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_client_form_media():
    return _run_query(list_client_form_media_service)


@client_form_config_bp.route("/media", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_client_form_media():
    return _run_command(create_client_form_media_service)


@client_form_config_bp.route("/media", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_client_form_media():
    return _run_command(update_client_form_media_service, return_data=False)


@client_form_config_bp.route("/media", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_client_form_media():
    return _run_command(delete_client_form_media_service, return_data=False)


@client_form_config_bp.route("/media/reorder", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def reorder_client_form_media():
    return _run_command(reorder_client_form_media_service)


# ── Post-submit redirect ───────────────────────────────────────────────────────

@client_form_config_bp.route("/redirects", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_client_form_redirects():
    return _run_query(list_client_form_redirects_service)


@client_form_config_bp.route("/redirects", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_client_form_redirect():
    return _run_command(create_client_form_redirect_service)


@client_form_config_bp.route("/redirects", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_client_form_redirect():
    return _run_command(update_client_form_redirect_service, return_data=False)


@client_form_config_bp.route("/redirects", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_client_form_redirect():
    return _run_command(delete_client_form_redirect_service, return_data=False)


@client_form_config_bp.route("/redirects/activate", methods=["POST"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def activate_client_form_redirect():
    return _run_command(activate_client_form_redirect_service)
