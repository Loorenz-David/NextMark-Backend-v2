# Logistic Inbound Event — `item_placed`

> **Problem:** An external logistics/WMS system needs to notify NextMark when a physical item
> has been placed at a warehouse location. The system sends a scan event payload including
> the order reference, the item SKU, and the shelf/location label. NextMark must update the
> item's `item_position` field and push a real-time update to the frontend.
>
> **Goal:** A new authenticated inbound endpoint that receives the `item_placed` event,
> resolves the matching items, stamps `item_position` with the scanned location string,
> and emits a socket event so the frontend refreshes the affected order's items.

---

## Incoming Request Contract

```
POST /api_v2/logistic/events/item-placed
Content-Type: application/json
x-api-key: <shared secret>
```

```json
{
  "event": "item_placed",
  "shopId": "shop-abc-123",
  "scanHistoryId": "scan-456",
  "orderId": "ord-client-789",
  "itemSku": "SKU-RED-XL",
  "logisticLocation": {
    "id": "loc-001",
    "location": "Shelf A-3",
    "updatedAt": "2026-04-22T10:30:00Z"
  }
}
```

**Authentication:** `x-api-key` header compared (timing-safe) against the `LOGISTIC_API_KEY`
env var. No JWT. No role decorator.

**orderId mapping:** `orderId` maps to `Order.external_order_id`. The external system sends
its external order identifier, not the internal integer PK and not NextMark `client_id`.

---

## Layer Map

```
router (api_v2/integration_logistic.py)
  → auth utility (commands/integration_logistic/auth/verify_api_key.py)
  → request parser (requests/integration_logistic/item_placed_request.py)
  → command (commands/integration_logistic/inbound/item_placed.py)
      → model query: Order by external_order_id
      → model query: Item by order_id + article_number
      → db write: item.item_position = location
      → event: build_order_edited_event → emit_order_events
```

---

## Files to Create

### File 1 — Config env vars
**File:** `Delivery_app_BK/config/default.py`

Add inside the `Config` class, under the existing integrations block:

```python
# Logistic integration
LOGISTIC_API_KEY = os.environ.get("LOGISTIC_API_KEY")
```

No model, no migration needed.

---

### File 2 — Package init files (empty)
Create the following empty `__init__.py` files so the new packages are importable:

- `Delivery_app_BK/services/commands/integration_logistic/__init__.py`
- `Delivery_app_BK/services/commands/integration_logistic/auth/__init__.py`
- `Delivery_app_BK/services/commands/integration_logistic/inbound/__init__.py`
- `Delivery_app_BK/services/requests/integration_logistic/__init__.py`

---

### File 3 — Auth utility
**File:** `Delivery_app_BK/services/commands/integration_logistic/auth/verify_api_key.py`

Following the same pattern as
`Delivery_app_BK/services/commands/integration_shopify/webhooks/verify_hook.py`.

```python
import hmac
import os
from Delivery_app_BK.errors import ValidationFailed

LOGISTIC_API_KEY = os.getenv("LOGISTIC_API_KEY")


def verify_api_key(headers: dict) -> None:
    received_key = headers.get("x-api-key") or headers.get("X-Api-Key")
    if not LOGISTIC_API_KEY or not received_key:
        raise ValidationFailed("Unauthorized")
    if not hmac.compare_digest(LOGISTIC_API_KEY, received_key):
        raise ValidationFailed("Unauthorized")
```

Key points:
- `hmac.compare_digest` prevents timing attacks — do not replace with `==`
- Both missing-key cases raise the same generic error — no information leakage
- Module-level `os.getenv` follows the pattern established in `verify_hook.py`

---

### File 4 — Request parser
**File:** `Delivery_app_BK/services/requests/integration_logistic/item_placed_request.py`

Following the dataclass parser pattern from
`Delivery_app_BK/services/requests/order/create_order.py`.

```python
from dataclasses import dataclass
from Delivery_app_BK.errors import ValidationFailed


@dataclass
class LogisticLocationPayload:
    id: str
    location: str
    updated_at: str


@dataclass
class ItemPlacedRequest:
    event: str
    shop_id: str
    scan_history_id: str
    order_id: str
    item_sku: str
    logistic_location: LogisticLocationPayload


def parse_item_placed_request(raw: dict) -> ItemPlacedRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Request body must be a JSON object.")

    event = raw.get("event")
    if event != "item_placed":
        raise ValidationFailed(f"Unsupported event type: {event!r}")

    for required in ("shopId", "scanHistoryId", "orderId", "itemSku", "logisticLocation"):
        if required not in raw:
            raise ValidationFailed(f"Missing required field: {required}")

    location_raw = raw["logisticLocation"]
    if not isinstance(location_raw, dict):
        raise ValidationFailed("logisticLocation must be an object.")
    if "location" not in location_raw:
        raise ValidationFailed("logisticLocation.location is required.")

    return ItemPlacedRequest(
        event=event,
        shop_id=str(raw["shopId"]),
        scan_history_id=str(raw["scanHistoryId"]),
        order_id=str(raw["orderId"]),
        item_sku=str(raw["itemSku"]),
        logistic_location=LogisticLocationPayload(
            id=str(location_raw.get("id", "")),
            location=str(location_raw["location"]),
            updated_at=str(location_raw.get("updatedAt", "")),
        ),
    )
```

---

### File 5 — Command
**File:** `Delivery_app_BK/services/commands/integration_logistic/inbound/item_placed.py`

```python
from Delivery_app_BK.models import db, Item, Order
from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.requests.integration_logistic.item_placed_request import ItemPlacedRequest
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events


def item_placed(request: ItemPlacedRequest) -> dict:
    # 1. Resolve order by external order id
    order: Order | None = (
        db.session.query(Order)
        .filter(
            Order.external_order_id == request.order_id,
        )
        .first()
    )
    if order is None:
        raise NotFound(f"Order not found for orderId: {request.order_id!r}")

    # 2. Find matching items — exact SKU match within the order
    items: list[Item] = (
        db.session.query(Item)
        .filter(
            Item.order_id == order.id,
            Item.article_number == request.item_sku,
        )
        .all()
    )
    if not items:
        return {
            "updated_count": 0,
            "warning": f"No items found for SKU {request.item_sku!r} in order {request.order_id!r}",
        }

    # 3. Stamp the location label on every matching item
    for item in items:
        item.item_position = request.logistic_location.location

    db.session.commit()

    # 4. Notify frontend — same pattern as update_item and create_item
    ctx = ServiceContext(identity={"team_id": order.team_id, "active_team_id": order.team_id})
    emit_order_events(ctx, [build_order_edited_event(order, changed_sections=["items"])])

    return {"updated_count": len(items)}
```

Key points:
- Exact `external_order_id ==` match is used for order resolution
- Exact `article_number ==` match (not `ilike`) — SKU from a scanner is always exact
- All items matching the SKU in that order are updated — the location label applies to every
  unit of the same SKU scanned to the same shelf
- If no items match, return `updated_count: 0` with a warning instead of raising `NotFound`
  — external systems should not receive 404s that trigger retries for a legitimate
  "already-processed or not-yet-created" scenario
- `emit_order_events` dispatches an `order.updated` socket event to the admin room, which
  triggers the frontend to refetch the order's items and display the new `item_position`

---

### File 6 — Router
**File:** `Delivery_app_BK/routers/api_v2/integration_logistic.py`

Following the blueprint pattern from other routers in `api_v2/`.

```python
from flask import Blueprint, request as flask_request
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.integration_logistic.auth.verify_api_key import verify_api_key
from Delivery_app_BK.services.requests.integration_logistic.item_placed_request import parse_item_placed_request
from Delivery_app_BK.services.commands.integration_logistic.inbound.item_placed import item_placed

logistic_bp = Blueprint("api_v2_logistic_bp", __name__)


@logistic_bp.route("/events/item-placed", methods=["POST"])
def inbound_item_placed():
    response = Response()

    try:
        verify_api_key(dict(flask_request.headers))
    except Exception as exc:
        return response.build_unsuccessful_response(str(exc)), 401

    raw = flask_request.get_json(silent=True) or {}

    ctx = ServiceContext(incoming_data=raw)
    outcome = run_service(
        lambda c: item_placed(parse_item_placed_request(raw)),
        ctx,
    )

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(outcome.data, warnings=ctx.warnings)
```

Key points:
- API key verification runs before `run_service` and returns `401` on failure — not the
  standard error envelope, since the caller is a machine and the distinction matters
- `parse_item_placed_request` validates the body shape; a `ValidationFailed` raised inside
  is caught by `run_service` and returned as a 400-style error through the standard envelope
- No `@jwt_required()`, no `@role_required()` — this endpoint is not scoped to the admin app

---

## Files to Modify

### Modification 1 — Router registration
**File:** `Delivery_app_BK/routers/api_v2/__init__.py`

**Step A — import** (add alongside the other integration blueprint imports):
```python
from .integration_logistic import logistic_bp
```

**Step B — add to the `"all"` dict** inside `_load_blueprints()`:
```python
"logistic_bp": logistic_bp,
```

Do NOT add to `admin_blueprints` — this blueprint must not have a scope guard installed,
since it is authenticated by API key and called by an external machine, not by a user session.

**Step C — register with URL prefix** inside `register_v2_blueprints()`:
```python
app.register_blueprint(bp["logistic_bp"], url_prefix="/api_v2/logistic")
```

Final endpoint path: `POST /api_v2/logistic/events/item-placed`

---

## Sequencing Notes

1. File 1 (config) first — API key config is needed by the auth utility
2. Files 2–5 (init files, auth, parser, command) can be written in any order
3. File 6 (router) last among new files — depends on auth, parser, and command
4. Modification 1 (registration) after File 6 — only register once the blueprint exists
5. No migration needed — no new DB table
6. No changes to `item.py`, `serialize_items.py`, or any existing item service — the
   `item_position` string field is already in place from the FK-to-label migration

---

## What Does Not Change

- All existing item endpoints (`/api_v2/item/`) — untouched
- The `ItemPosition` table and its endpoints — untouched
- The `update_item_position` command — untouched
- JWT-authenticated flow — this endpoint sits alongside it, not replacing it
- The socket contract — `order.updated` with `changed_sections: ["items"]` is the
  existing pattern; no new event type is needed
