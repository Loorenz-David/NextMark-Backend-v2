from typing import Any, Dict, List, Optional

from Delivery_app_BK.models import (
    ClientFormMedia,
    ClientFormRule,
    ClientFormSettings,
    ClientFormTermsVersion,
)
from ...context import ServiceContext
from ..utils import map_return_values

# Applied when a team has never saved a settings row.
DEFAULT_SETTINGS = {
    "terms_enabled": False,
    "require_acceptance": False,
    "show_rules": True,
    "show_media": True,
}


def serialize_client_form_settings(instance: Optional[ClientFormSettings]) -> Dict[str, Any]:
    if instance is None:
        return {"id": None, "client_id": None, "updated_at": None, **DEFAULT_SETTINGS}

    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "terms_enabled": instance.terms_enabled,
        "require_acceptance": instance.require_acceptance,
        "show_rules": instance.show_rules,
        "show_media": instance.show_media,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }


def serialize_terms_version(instance: ClientFormTermsVersion) -> Dict[str, Any]:
    return {
        "id": instance.id,
        "version_number": instance.version_number,
        "content": instance.content,
        "is_active": instance.is_active,
        "created_at": instance.created_at.isoformat() if instance.created_at else None,
        "created_by_user_id": instance.created_by_user_id,
    }


def serialize_terms_versions(
    instances: List[ClientFormTermsVersion],
    ctx: ServiceContext,
):
    unpacked = [serialize_terms_version(instance) for instance in instances]
    return map_return_values(unpacked, ctx, "client_form_terms_version")


def serialize_client_form_rule(instance: ClientFormRule) -> Dict[str, Any]:
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "position": instance.position,
        "enabled": instance.enabled,
        "title": instance.title,
        "body": instance.body,
        "icon": instance.icon,
        "image_url": instance.image_url,
    }


def serialize_client_form_rules(instances: List[ClientFormRule], ctx: ServiceContext):
    unpacked = [serialize_client_form_rule(instance) for instance in instances]
    return map_return_values(unpacked, ctx, "client_form_rule")


def serialize_client_form_media_item(instance: ClientFormMedia) -> Dict[str, Any]:
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "placement": instance.placement,
        "position": instance.position,
        "enabled": instance.enabled,
        "url": instance.url,
        "storage_key": instance.storage_key,
        "alt_text": instance.alt_text,
        "link_url": instance.link_url,
        "title": instance.title,
        "description": instance.description,
    }


def serialize_client_form_media(instances: List[ClientFormMedia], ctx: ServiceContext):
    unpacked = [serialize_client_form_media_item(instance) for instance in instances]
    return map_return_values(unpacked, ctx, "client_form_media")
