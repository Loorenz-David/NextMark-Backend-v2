import os

from urllib.parse import urlencode
import secrets
from datetime import datetime, timedelta, timezone

from flask_jwt_extended import jwt_required, get_jwt_identity

from Delivery_app_BK.errors import ValidationFailed

from ....context import ServiceContext
from .oauth_state import save_oauth_state




SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOPIFY_REDIRECT_URI = os.getenv("SHOPIFY_REDIRECT_URI")

def connect_to_shopify_store ( ctx: ServiceContext, shop ):


    if not shop:
        raise ValidationFailed("Missing shop parameter")

    scopes = ",".join([
        "read_products",
        "write_products",
        "read_inventory",
        "write_inventory",
        "read_locations",
    ])

    redirect_uri = SHOPIFY_REDIRECT_URI
    state = secrets.token_urlsafe(32)

    save_oauth_state(
        state=state,
        user_id=ctx.user_id,
        team_id=ctx.team_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    params = {
        "client_id": SHOPIFY_CLIENT_ID,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }

    auth_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"

    return {
        "auth_url": auth_url
    }