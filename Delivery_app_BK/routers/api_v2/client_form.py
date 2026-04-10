"""
Routers for the client-form-link feature.

  Authenticated (admin):
    POST /api/v2/orders/<order_id>/client-form-link  → generate / regenerate token
        POST /api/v2/orders/<order_id>/client-form-link/send → generate / regenerate and send token

  Public (no auth — token acts as the credential):
    GET  /api/v2/public/client-form/<token>           → fetch safe order data for the form
    POST /api/v2/public/client-form/<token>           → submit client info (invalidates token)
"""

import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.errors import DomainError
from Delivery_app_BK.errors.client_form import (
    TokenInvalidError,
    TokenExpiredError,
    TokenAlreadyUsedError,
)
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.commands.order.client_form.generate_token import generate_client_form_token
from Delivery_app_BK.services.commands.order.client_form.get_client_form import get_client_form_data
from Delivery_app_BK.services.commands.order.client_form.send_link import send_client_form_link
from Delivery_app_BK.services.commands.order.client_form.submit_client_form import submit_client_form


client_form_bp = Blueprint("client_form", __name__)
public_client_form_bp = Blueprint("public_client_form", __name__)

CLIENT_FORM_BASE_URL = os.environ.get("CLIENT_FORM_BASE_URL", "https://forms.nextmark.app")


# ── Authenticated ──────────────────────────────────────────────────────────────

@client_form_bp.route("/orders/<int:order_id>/client-form-link", methods=["POST"])
@jwt_required()
def generate_client_form_link(order_id: int):
    """Generate (or regenerate) a secure client-form link for the given order."""
    identity = get_jwt()
    team_id = identity.get("active_team_id") or identity.get("team_id")

    response = Response()
    try:
        result = generate_client_form_token(order_id, team_id)
        form_url = f"{CLIENT_FORM_BASE_URL}/form/{result['raw_token']}"
        return response.build_successful_response({
            "form_url": form_url,
            "expires_at": result["expires_at"].isoformat(),
        })
    except DomainError as e:
        return response.build_unsuccessful_response(e)


@client_form_bp.route("/orders/<int:order_id>/client-form-link/send", methods=["POST"])
@jwt_required()
def send_client_form_link_route(order_id: int):
    """Generate (or regenerate) and send the secure client-form link for the given order."""
    identity = get_jwt()
    team_id = identity.get("active_team_id") or identity.get("team_id")
    payload = request.get_json(silent=True) or {}

    response = Response()
    try:
        result = send_client_form_link(
            order_id=order_id,
            team_id=team_id,
            base_url=CLIENT_FORM_BASE_URL,
            identity=identity,
            payload=payload,
        )
        return response.build_successful_response({
            "form_url": result["form_url"],
            "expires_at": result["expires_at"].isoformat(),
            "reused": result["reused"],
            "send_results": result["send_results"],
        })
    except DomainError as e:
        return response.build_unsuccessful_response(e)


# ── Public ─────────────────────────────────────────────────────────────────────

@public_client_form_bp.route("/public/client-form/<string:token>", methods=["GET"])
def get_client_form(token: str):
    """Return the safe order data needed to render the public client form."""
    try:
        data = get_client_form_data(token)
        return jsonify(data), 200
    except TokenAlreadyUsedError as e:
        return jsonify({"error": e.message, "code": e.code}), 409
    except TokenExpiredError as e:
        return jsonify({"error": e.message, "code": e.code}), 410
    except TokenInvalidError as e:
        return jsonify({"error": e.message, "code": e.code}), 404
    except DomainError as e:
        return jsonify({"error": e.message, "code": e.code}), 500


@public_client_form_bp.route("/public/client-form/<string:token>", methods=["POST"])
def submit_client_form_route(token: str):
    """Accept and persist the client's submitted information."""
    payload = request.get_json(force=True) or {}
    try:
        result = submit_client_form(token, payload)
        return jsonify(result), 200
    except TokenAlreadyUsedError as e:
        return jsonify({"error": e.message, "code": e.code}), 409
    except TokenExpiredError as e:
        return jsonify({"error": e.message, "code": e.code}), 410
    except TokenInvalidError as e:
        return jsonify({"error": e.message, "code": e.code}), 404
    except DomainError as e:
        return jsonify({"error": e.message, "code": e.code}), 500
