"""
Public order tracking endpoint.

GET /api_v2/public/order-tracking/<token>
- No auth required.
- The token acts as the credential; it is validated (via its SHA-256 hash)
  inside the query service.
"""

from flask import Blueprint, jsonify

from Delivery_app_BK.errors import DomainError, NotFound
from Delivery_app_BK.services.queries.order.get_order_tracking import get_order_tracking


public_order_tracking_bp = Blueprint("public_order_tracking", __name__)


@public_order_tracking_bp.route(
    "/public/order-tracking/<string:token>", methods=["GET"]
)
def track_order(token: str):
    """Return customer-safe tracking data for the order identified by *token*."""
    try:
        data = get_order_tracking(token)
        return jsonify(data), 200
    except NotFound as e:
        return jsonify({"error": "Not found", "code": "not_found"}), 404
    except DomainError as e:
        return jsonify({"error": e.message, "code": e.code}), 500
