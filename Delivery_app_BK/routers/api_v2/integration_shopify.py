import os
from flask import Blueprint, request, redirect, render_template
from flask_jwt_extended import jwt_required, get_jwt


from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service

from Delivery_app_BK.services.commands.integration_shopify.auth import (
    connect_to_shopify_store,
    handle_shopify_oauth_callback,
    handle_shopify_unisntall,
    remove_shopify_integration,
    )
from Delivery_app_BK.services.commands.integration_shopify.webhooks import (
    verify_shopify_webhook
)
from Delivery_app_BK.services.queries.integration_shopify.get_shopify_details import (
    get_shopify_details,
)


from ..http.response import Response

shopify_bp = Blueprint("api_v2_integration_shopify", __name__)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")



@shopify_bp.route("/connect", methods=["GET"])
@jwt_required()
def connect_shopify():
    identity = get_jwt()
    shop = request.args.get("shop")  # my-store.myshopify.com
    ctx = ServiceContext(
        identity = identity
    )

    outcome = run_service( lambda c: connect_to_shopify_store( c, shop), ctx)

    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@shopify_bp.route("/<integration_id>", methods=["GET"])
@jwt_required()
def get_shopify_integration(integration_id: str):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: get_shopify_details(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@shopify_bp.route("/<integration_id>", methods=["DELETE"])
@jwt_required()
def delete_shopify_integration(integration_id: str):
    identity = get_jwt()
    ctx = ServiceContext(
        identity=identity,
    )
    outcome = run_service(lambda c: remove_shopify_integration(c, integration_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )
    
   
# OAuth callback is unauthenticated; user binding is resolved via OAuth state
@shopify_bp.route("/oauth/callback", methods=["GET"])
def shopify_oauth_callback():
    ctx = ServiceContext()
    response = Response()
    outcome = run_service(
        lambda c: handle_shopify_oauth_callback(c, request.args.to_dict()),
        ctx
    )
   
    if outcome.error:
        return response.build_unsuccessful_response(error= outcome.error)

    return redirect(outcome.data["redirect_url"])


@shopify_bp.route("/app")
def shopify_app_home():
    shop = request.args.get("shop")
    host = request.args.get("host")
    status = request.args.get("status")
    embedded = request.args.get("embedded") == "1"
    return render_template("shopify_app.html", 
                           shop=shop,
                           host=host,
                           embedded=embedded,
                           status=status,
                           front_url=FRONTEND_ORIGIN
                           )


@shopify_bp.route("/app-uninstalled", methods=["POST"])
def shopify_app_uninstalled():
    raw_body = request.get_data()
    headers = request.headers

    # 1. Verify webhook authenticity (REQUIRED)¨
    try:
        verify_shopify_webhook(raw_body, headers)
    except Exception:
        return "", 401

    shop_domain = headers.get("X-Shopify-Shop-Domain")

    if not shop_domain:
        return "", 200  

    try:

        handle_shopify_unisntall(shop_domain)
    except Exception:
        pass

    return "", 200


@shopify_bp.route("/gdpr/customers/data_request", methods=["POST"])
def gdpr_data_request():
    verify_shopify_webhook(request.data, request.headers)
    return "", 200


@shopify_bp.route("/gdpr/customers/redact", methods=["POST"])
def gdpr_customer_redact():
    verify_shopify_webhook(request.data, request.headers)
    return "", 200


@shopify_bp.route("/gdpr/shop/redact", methods=["POST"])
def gdpr_shop_redact():
    verify_shopify_webhook(request.data, request.headers)
    return "", 200
