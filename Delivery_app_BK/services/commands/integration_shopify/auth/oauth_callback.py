import os
import hmac
import hashlib
import requests

from datetime import datetime, timezone

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import OAuthState

from ....context import ServiceContext
from .oauth_state import get_oauth_state, delete_oauth_state
from .save_shopify_integration import save_shopify_integration
from ..webhooks import create_shopify_webhook


SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOPIFY_FRONTEND_URL = os.getenv("FRONTEND_ORIGIN")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")

def verify_shopify_hmac(params: dict):
    
    params = params.copy()

    received_hmac = params.pop("hmac", None)
    if not received_hmac:
        raise ValidationFailed("Missing HMAC")

    message = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    calculated_hmac = hmac.new(
        SHOPIFY_CLIENT_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hmac, received_hmac):
        raise ValidationFailed("Invalid HMAC signature")
    

def exchange_code_for_token(shop: str, code: str) -> str:
    url = f"https://{shop}/admin/oauth/access_token"

    payload = {
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "code": code,
    }

    response = requests.post(url, json=payload, timeout=10)

    if response.status_code != 200:
        raise ValidationFailed("Failed to retrieve Shopify access token")

    data: dict = response.json()
    access_token = data.get("access_token")
    scopes = data.get("scope")
    if not access_token:
        raise ValidationFailed("Shopify did not return an access token")

    return access_token, scopes

def handle_shopify_oauth_callback(ctx: ServiceContext, params):
    """
        Handles Shopify OAuth callback.

        Flow:
        1. Validate params
        2. Resolve user via OAuth state
        3. Verify Shopify HMAC
        4. Exchange code for access token
    
    """

    shop = params.get("shop")
    code = params.get("code")
    state = params.get("state")
    host = params.get("host")

    if not shop or not code:
        raise ValidationFailed("Missing shop or code")

    if not state:
        raise ValidationFailed("Missing OAuth state")

    
    # fetch and validate stored state (pseudo persistence hook)
    oauth_state: OAuthState = get_oauth_state(state)
    if not oauth_state or oauth_state.expires_at < datetime.now(timezone.utc):
        raise ValidationFailed("Invalid or expired OAuth state")


    # bind user to context
    ctx.identity = {"user_id": oauth_state.user_id, "team_id": oauth_state.team_id}


    # 1. Verify request integrity
    verify_shopify_hmac(params) 

    # 2. Exchange code → token
    [access_token, scopes] = exchange_code_for_token(shop, code)
  
    # consume state so it cannot be reused
    delete_oauth_state(state)

    # 3. Persist connection (pseudo-code)
    # ------------------------------------------------
    ctx.incoming_data = {
        "team_id":ctx.team_id,
        "user_id":ctx.user_id,
        "shop":shop,
        "access_token":access_token,
        "scopes":scopes
    }
    
    save_shopify_integration(ctx)

    create_shopify_webhook(
        shop=shop,
        access_token=access_token,
        topic="orders/create",
        address=f"{BACKEND_PUBLIC_URL}/webhooks/shopify/orders"
    )
    create_shopify_webhook(
    shop=shop,
    access_token=access_token,
    topic="app/uninstalled",
    address=f"{BACKEND_PUBLIC_URL}/api_v2/shopify/app-uninstalled"
)
    # ------------------------------------------------

    # 4. Return frontend redirect
    return {
        "redirect_url": (
            f"{FRONTEND_ORIGIN}/settings/integrations/status"
            f"?integration=shopify&status=connected&shop={shop}&embedded=1&host={host}"         
        )
    }

