from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.redis.client import get_current_redis_connection
from Delivery_app_BK.services.infra.redis.keys import build_ai_proposal_apply_key
from Delivery_app_BK.services.commands.item.create.create_item_property import (
    create_item_property as create_item_property_service,
)
from Delivery_app_BK.services.commands.item.create.create_item_type import (
    create_item_type as create_item_type_service,
)
from Delivery_app_BK.services.commands.item.update.update_item_property import (
    update_item_property as update_item_property_service,
)
from Delivery_app_BK.services.commands.item.update.update_item_type import (
    update_item_type as update_item_type_service,
)
from Delivery_app_BK.services.queries.item_property.get_item_property import (
    get_item_property as get_item_property_service,
)
from Delivery_app_BK.services.queries.item_property.list_item_properties import (
    list_item_properties as list_item_properties_service,
)
from Delivery_app_BK.services.queries.item_type.get_item_type import (
    get_item_type as get_item_type_service,
)
from Delivery_app_BK.services.queries.item_type.list_item_types import (
    list_item_types as list_item_types_service,
)

_APPLIED_PROPOSAL_HASHES: set[str] = set()
_PROPOSAL_METRICS_COUNTERS: Counter[str] = Counter()
logger = logging.getLogger(__name__)

PROPOSAL_STATUS_PENDING_CONFIRM = "pending_confirm"
PROPOSAL_STATUS_APPLIED = "applied"
PROPOSAL_STATUS_CANCELLED = "cancelled"
PROPOSAL_STATUS_EXPIRED = "expired"


class ProposalLifecycleValidationFailed(ValidationFailed):
    code = "proposal_invalid_state"


class ProposalAlreadyAppliedError(ProposalLifecycleValidationFailed):
    code = "proposal_already_applied"


class ProposalCancelledError(ProposalLifecycleValidationFailed):
    code = "proposal_cancelled"


class ProposalExpiredError(ProposalLifecycleValidationFailed):
    code = "proposal_expired"


class ProposalConflictError(ProposalLifecycleValidationFailed):
    code = "proposal_conflict"


def list_item_types_config_tool(
    ctx: ServiceContext,
    name: str | None = None,
    limit: int = 50,
    sort: str = "id_desc",
) -> dict:
    filters: dict[str, Any] = {"limit": limit, "sort": sort}
    if name:
        filters["name"] = name

    ctx.query_params = {**ctx.query_params, **filters}
    result = list_item_types_service(ctx)

    item_types = result.get("item_types") or []
    return {
        "item_types": item_types,
        "count": len(item_types),
        "item_types_pagination": result.get("item_types_pagination"),
    }


def list_item_properties_config_tool(
    ctx: ServiceContext,
    name: str | None = None,
    field_type: str | None = None,
    required: bool | None = None,
    limit: int = 50,
    sort: str = "id_desc",
) -> dict:
    filters: dict[str, Any] = {"limit": limit, "sort": sort}
    if name:
        filters["name"] = name
    if field_type:
        filters["field_type"] = field_type
    if required is not None:
        filters["required"] = required

    ctx.query_params = {**ctx.query_params, **filters}
    result = list_item_properties_service(ctx)

    item_properties = result.get("item_properties") or []
    return {
        "item_properties": item_properties,
        "count": len(item_properties),
        "item_properties_pagination": result.get("item_properties_pagination"),
    }


def get_item_type_config_tool(ctx: ServiceContext, item_type_id: int) -> dict:
    return get_item_type_service(item_type_id, ctx)


def get_item_property_config_tool(ctx: ServiceContext, item_property_id: int) -> dict:
    return get_item_property_service(item_property_id, ctx)


def create_item_type_config_tool(
    ctx: ServiceContext,
    name: str,
    property_ids: list[int] | None = None,
) -> dict:
    fields: dict[str, Any] = {"name": name}
    if property_ids is not None:
        fields["properties"] = property_ids

    ctx.incoming_data = {"fields": fields}
    result = create_item_type_service(ctx)

    created = _extract_first_created(result, "item_type")
    return {
        "status": "created",
        "item_type": created,
        "result": result,
    }


def create_item_property_config_tool(
    ctx: ServiceContext,
    name: str,
    field_type: str = "text",
    required: bool = False,
    options: list[Any] | None = None,
    item_type_ids: list[int] | None = None,
) -> dict:
    fields: dict[str, Any] = {
        "name": name,
        "field_type": field_type,
        "required": required,
    }
    if options is not None:
        fields["options"] = options
    if item_type_ids is not None:
        fields["item_types"] = item_type_ids

    ctx.incoming_data = {"fields": fields}
    result = create_item_property_service(ctx)

    created = _extract_first_created(result, "item_property")
    return {
        "status": "created",
        "item_property": created,
        "result": result,
    }


def update_item_type_config_tool(
    ctx: ServiceContext,
    item_type_id: int,
    fields: dict[str, Any],
) -> dict:
    if not fields:
        raise ValidationFailed("fields must be a non-empty dict.")

    ctx.incoming_data = {
        "targets": [
            {
                "target_id": item_type_id,
                "fields": fields,
            }
        ]
    }
    updated_ids = update_item_type_service(ctx)
    return {
        "status": "updated",
        "item_type_id": item_type_id,
        "updated_ids": updated_ids,
        "fields": fields,
    }


def update_item_property_config_tool(
    ctx: ServiceContext,
    item_property_id: int,
    fields: dict[str, Any],
) -> dict:
    if not fields:
        raise ValidationFailed("fields must be a non-empty dict.")

    ctx.incoming_data = {
        "targets": [
            {
                "target_id": item_property_id,
                "fields": fields,
            }
        ]
    }
    updated_ids = update_item_property_service(ctx)
    return {
        "status": "updated",
        "item_property_id": item_property_id,
        "updated_ids": updated_ids,
        "fields": fields,
    }


def link_properties_to_item_type_tool(
    ctx: ServiceContext,
    item_type_id: int,
    property_ids: list[int],
    merge: bool = True,
) -> dict:
    if not property_ids:
        raise ValidationFailed("property_ids must be a non-empty list.")

    desired_ids = [int(pid) for pid in property_ids]
    if merge:
        found = get_item_type_service(item_type_id, ctx)
        item_type = found.get("item_type") or {}
        existing_ids = item_type.get("properties") or []
        desired_ids = sorted(set(existing_ids + desired_ids))

    return update_item_type_config_tool(
        ctx,
        item_type_id=item_type_id,
        fields={"properties": desired_ids},
    )


def _extract_first_created(result: dict, key: str) -> dict | None:
    raw = result.get(key)
    if isinstance(raw, list) and raw:
        first = raw[0]
        return first if isinstance(first, dict) else None
    if isinstance(raw, dict):
        return raw
    return None


def create_item_taxonomy_proposal_tool(
    ctx: ServiceContext,
    item_types: list[dict[str, Any]],
    proposal_name: str | None = None,
) -> dict:
    """
    Build a normalized item taxonomy proposal and return an approval token.

    Proposal shape:
    {
      "item_types": [
        {
          "name": "furniture",
          "properties": [
            {
              "name": "material",
              "field_type": "select",
              "required": true,
              "options": ["oak", "pine"]
            }
          ]
        }
      ]
    }
    """
    if not isinstance(item_types, list) or not item_types:
        raise ValidationFailed("item_types must be a non-empty list.")

    normalized_types: list[dict[str, Any]] = []
    for item_type in item_types:
        if not isinstance(item_type, dict):
            raise ValidationFailed("Each item type entry must be an object.")

        name = str(item_type.get("name") or "").strip()
        if not name:
            raise ValidationFailed("Each item type requires a non-empty name.")

        properties_raw = item_type.get("properties") or []
        if not isinstance(properties_raw, list):
            raise ValidationFailed("item_type.properties must be a list.")

        normalized_properties: list[dict[str, Any]] = []
        for prop in properties_raw:
            if not isinstance(prop, dict):
                raise ValidationFailed("Each property entry must be an object.")

            prop_name = str(prop.get("name") or "").strip()
            if not prop_name:
                raise ValidationFailed("Each property requires a non-empty name.")

            field_type = str(prop.get("field_type") or "text").strip() or "text"
            required = bool(prop.get("required", False))
            options = prop.get("options")

            normalized_property = {
                "name": prop_name,
                "field_type": field_type,
                "required": required,
            }
            if options is not None:
                if not isinstance(options, list):
                    raise ValidationFailed("property.options must be a list when provided.")
                normalized_property["options"] = options

            normalized_properties.append(normalized_property)

        normalized_types.append({"name": name, "properties": normalized_properties})

    created_at = _utcnow()
    expires_at = created_at + timedelta(seconds=_proposal_ttl_seconds())

    proposal = {
        "proposal_name": (proposal_name or "item-taxonomy-proposal").strip(),
        "item_types": normalized_types,
        "meta": {
            "status": PROPOSAL_STATUS_PENDING_CONFIRM,
            "created_at": _format_utc_iso(created_at),
            "expires_at": _format_utc_iso(expires_at),
            "version": 1,
        },
    }
    approval_token = _build_proposal_token(proposal)
    logger.info(
        "AI proposal created | proposal_name=%s | status=%s | item_types=%d | expires_at=%s",
        proposal.get("proposal_name"),
        proposal["meta"]["status"],
        len(normalized_types),
        proposal["meta"]["expires_at"],
    )
    _record_proposal_metric("ai_proposal_create", outcome="success")
    return {
        "status": "proposal_ready",
        "requires_approval": True,
        "approval_token": approval_token,
        "proposal": proposal,
        "summary": _summarize_taxonomy_proposal(proposal),
    }


def apply_item_taxonomy_proposal_tool(
    ctx: ServiceContext,
    proposal: dict[str, Any],
    approval_token: str,
    approved: bool = False,
) -> dict:
    """
    Apply a previously prepared taxonomy proposal.
    Requires approved=true and a valid token that matches the proposal payload.
    """
    try:
        if not approved:
            raise ValidationFailed("approved=true is required before applying taxonomy changes.")

        if not isinstance(proposal, dict):
            raise ValidationFailed("proposal must be an object.")

        proposal_meta = _normalize_proposal_meta(proposal)
        _assert_proposal_can_transition_to_applied(proposal_meta)

        expected_token = _build_proposal_token(proposal)
        if approval_token != expected_token:
            raise ProposalConflictError("approval_token does not match the provided proposal.")

        proposal_hash = _build_proposal_hash(proposal)
        if not _mark_proposal_applied_once(proposal_hash):
            raise ProposalAlreadyAppliedError("This proposal has already been applied.")

        item_types = proposal.get("item_types") or []
        if not isinstance(item_types, list) or not item_types:
            raise ValidationFailed("proposal.item_types must be a non-empty list.")

        created_item_types = 0
        reused_item_types = 0
        created_properties = 0
        reused_properties = 0
        links_applied = 0

        for item_type in item_types:
            if not isinstance(item_type, dict):
                raise ValidationFailed("Each proposal item type must be an object.")

            type_name = str(item_type.get("name") or "").strip()
            if not type_name:
                raise ValidationFailed("Proposal item type name is required.")

            property_ids: list[int] = []
            properties = item_type.get("properties") or []
            if not isinstance(properties, list):
                raise ValidationFailed("Proposal item type properties must be a list.")

            for prop in properties:
                if not isinstance(prop, dict):
                    raise ValidationFailed("Each proposal property must be an object.")

                prop_name = str(prop.get("name") or "").strip()
                if not prop_name:
                    raise ValidationFailed("Proposal property name is required.")

                existing_prop = _find_item_property_by_name(ctx, prop_name)
                if existing_prop is not None:
                    property_ids.append(int(existing_prop["id"]))
                    reused_properties += 1
                else:
                    created_prop = create_item_property_config_tool(
                        ctx,
                        name=prop_name,
                        field_type=str(prop.get("field_type") or "text"),
                        required=bool(prop.get("required", False)),
                        options=prop.get("options"),
                    )
                    item_property = created_prop.get("item_property") or {}
                    if not isinstance(item_property, dict) or item_property.get("id") is None:
                        raise ValidationFailed(f"Failed to create property '{prop_name}'.")
                    property_ids.append(int(item_property["id"]))
                    created_properties += 1

            existing_type = _find_item_type_by_name(ctx, type_name)
            if existing_type is not None:
                type_id = int(existing_type["id"])
                reused_item_types += 1
            else:
                created_type = create_item_type_config_tool(ctx, name=type_name)
                item_type_created = created_type.get("item_type") or {}
                if not isinstance(item_type_created, dict) or item_type_created.get("id") is None:
                    raise ValidationFailed(f"Failed to create item type '{type_name}'.")
                type_id = int(item_type_created["id"])
                created_item_types += 1

            if property_ids:
                link_properties_to_item_type_tool(
                    ctx,
                    item_type_id=type_id,
                    property_ids=property_ids,
                    merge=True,
                )
                links_applied += 1

        result = {
            "status": "applied",
            "approval_token": approval_token,
            "proposal_hash": proposal_hash,
            "proposal_meta": {
                **proposal_meta,
                "status": PROPOSAL_STATUS_APPLIED,
                "applied_at": _format_utc_iso(_utcnow()),
            },
            "created_item_types": created_item_types,
            "reused_item_types": reused_item_types,
            "created_properties": created_properties,
            "reused_properties": reused_properties,
            "links_applied": links_applied,
        }

        logger.info(
            "AI proposal applied | proposal_hash=%s | created_item_types=%d | reused_item_types=%d | created_properties=%d | reused_properties=%d | links_applied=%d",
            proposal_hash,
            created_item_types,
            reused_item_types,
            created_properties,
            reused_properties,
            links_applied,
        )
        _record_proposal_metric("ai_proposal_apply", outcome="success")
        return result
    except ValidationFailed as exc:
        error_code = getattr(exc, "code", "bad_request")
        _record_proposal_metric("ai_proposal_apply", outcome="failure", error_code=error_code)
        logger.warning("AI proposal apply rejected | error_code=%s | error=%s", error_code, exc)
        raise
    except Exception as exc:
        _record_proposal_metric("ai_proposal_apply", outcome="failure", error_code="internal_error")
        logger.exception("AI proposal apply failed unexpectedly | error=%s", exc)
        raise


def _find_item_type_by_name(ctx: ServiceContext, name: str) -> dict[str, Any] | None:
    original_query_params = dict(ctx.query_params)
    try:
        result = list_item_types_config_tool(ctx, name=name, limit=50)
    finally:
        ctx.query_params = original_query_params

    for item_type in result.get("item_types") or []:
        if isinstance(item_type, dict) and str(item_type.get("name") or "").strip().lower() == name.lower():
            return item_type
    return None


def _find_item_property_by_name(ctx: ServiceContext, name: str) -> dict[str, Any] | None:
    original_query_params = dict(ctx.query_params)
    try:
        result = list_item_properties_config_tool(ctx, name=name, limit=50)
    finally:
        ctx.query_params = original_query_params

    for item_property in result.get("item_properties") or []:
        if isinstance(item_property, dict) and str(item_property.get("name") or "").strip().lower() == name.lower():
            return item_property
    return None


def _build_proposal_token(proposal: dict[str, Any]) -> str:
    canonical = json.dumps(proposal, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"tax_{digest[:16]}"


def _build_proposal_hash(proposal: dict[str, Any]) -> str:
    canonical = json.dumps(proposal, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _proposal_apply_ttl_seconds() -> int:
    try:
        return int(current_app.config.get("AI_PROPOSAL_APPLY_IDEMPOTENCY_TTL_SECONDS", 60 * 60 * 24 * 30))
    except RuntimeError:
        # No Flask app context (for example in isolated unit tests).
        return 60 * 60 * 24 * 30


def _proposal_ttl_seconds() -> int:
    try:
        return int(current_app.config.get("AI_PROPOSAL_TTL_SECONDS", 60 * 60 * 24 * 30))
    except RuntimeError:
        # No Flask app context (for example in isolated unit tests).
        return 60 * 60 * 24 * 30


def _mark_proposal_applied_once(proposal_hash: str) -> bool:
    try:
        redis = get_current_redis_connection()
        redis_key = build_ai_proposal_apply_key(proposal_hash)
        claimed = redis.set(redis_key, "1", nx=True, ex=_proposal_apply_ttl_seconds())
        return bool(claimed)
    except Exception as exc:
        # Keep tests and no-redis environments functional while still enforcing
        # idempotency best-effort.
        logger.warning("Redis idempotency unavailable, using local fallback | error=%s", exc)
        if proposal_hash in _APPLIED_PROPOSAL_HASHES:
            return False
        _APPLIED_PROPOSAL_HASHES.add(proposal_hash)
        return True


def _normalize_proposal_meta(proposal: dict[str, Any]) -> dict[str, Any]:
    raw_meta = proposal.get("meta")
    if not isinstance(raw_meta, dict):
        # Backward compatibility for legacy proposals without metadata.
        return {
            "status": PROPOSAL_STATUS_PENDING_CONFIRM,
            "created_at": None,
            "expires_at": None,
            "version": 0,
        }

    return {
        "status": str(raw_meta.get("status") or PROPOSAL_STATUS_PENDING_CONFIRM),
        "created_at": raw_meta.get("created_at"),
        "expires_at": raw_meta.get("expires_at"),
        "version": int(raw_meta.get("version") or 1),
    }


def _assert_proposal_can_transition_to_applied(meta: dict[str, Any]) -> None:
    status = str(meta.get("status") or "").strip()
    if status == PROPOSAL_STATUS_APPLIED:
        raise ProposalAlreadyAppliedError("This proposal has already been applied.")
    if status == PROPOSAL_STATUS_CANCELLED:
        raise ProposalCancelledError("This proposal was cancelled and cannot be applied.")
    if status == PROPOSAL_STATUS_EXPIRED:
        raise ProposalExpiredError("This proposal has expired and can no longer be applied.")
    if status != PROPOSAL_STATUS_PENDING_CONFIRM:
        raise ProposalLifecycleValidationFailed(f"Proposal in status '{status}' cannot transition to applied.")

    expires_at_raw = meta.get("expires_at")
    if not isinstance(expires_at_raw, str) or not expires_at_raw.strip():
        return

    expires_at = _parse_utc_iso(expires_at_raw)
    if expires_at is None:
        raise ValidationFailed("proposal.meta.expires_at must be a valid UTC ISO-8601 timestamp.")
    if _utcnow() >= expires_at:
        raise ProposalExpiredError("This proposal has expired and can no longer be applied.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc_iso(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _summarize_taxonomy_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    item_types = proposal.get("item_types") or []
    properties_count = 0
    for item_type in item_types:
        if isinstance(item_type, dict):
            properties = item_type.get("properties") or []
            if isinstance(properties, list):
                properties_count += len(properties)

    return {
        "item_types_count": len(item_types),
        "properties_count": properties_count,
    }


def _record_proposal_metric(metric_name: str, *, outcome: str, error_code: str = "none") -> None:
    key = f"{metric_name}|outcome={outcome}|error_code={error_code}"
    _PROPOSAL_METRICS_COUNTERS[key] += 1


def get_proposal_metrics_snapshot() -> dict[str, int]:
    """Return lightweight in-process proposal metrics counters for diagnostics/tests."""
    return dict(_PROPOSAL_METRICS_COUNTERS)
