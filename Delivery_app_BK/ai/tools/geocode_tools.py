from __future__ import annotations

import logging

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.geocoding.orchestrator import geocode_address
from Delivery_app_BK.services.context import ServiceContext

logger = logging.getLogger(__name__)


def geocode_address_tool(
    ctx: ServiceContext,
    q: str,
    country_hint: str | None = None,
) -> dict:
    """
    Resolve a free-text address string to a structured address object
    that matches ADDRESS_SCHEMA (street_address, postal_code, city, country,
    coordinates.lat/lng).

    ALWAYS call this before create_order or update_order when the user provides
    a delivery address as plain text. Pass the returned address_object directly
    as client_address.

    Parameters:
        q:            Free-text address  (e.g. "Kungsgatan 5, Stockholm").
                      Include as much detail as the user provided: street, city,
                      postal code, country.
        country_hint: ISO 3166-1 alpha-2 country code to narrow results (e.g. "SE").
                      ALWAYS set this when the team's operating country is known.
    """
    if not q or not q.strip():
        raise ValidationFailed("q must be a non-empty address string.")

    resolved_country_hint = country_hint or ctx.default_country_code or None
    country_hint_source = "explicit" if country_hint else ("team_default" if ctx.default_country_code else "none")

    result = geocode_address(q.strip(), country_hint=resolved_country_hint)

    if result is None:
        logger.warning(
            "geocode_address_tool | no result | q=%r | country_hint=%r | source=%s",
            q,
            resolved_country_hint,
            country_hint_source,
        )
        return {
            "found": False,
            "q": q,
            "address_object": None,
            "used_country_hint": resolved_country_hint,
            "country_hint_source": country_hint_source,
            "can_create_without_client_address": True,
            "hint": (
                "No geocoding result was found for this query. "
                "Ask the user to provide a more specific address including street, city, and country, "
                "or proceed with create_order omitting client_address (the order can be updated later)."
            ),
        }

    address_object = result.to_address_dict()

    logger.info(
        "geocode_address_tool | q=%r | resolved=%r | lat=%s lng=%s",
        q,
        result.formatted_address,
        result.lat,
        result.lng,
    )
    return {
        "found": True,
        "q": q,
        "formatted_address": result.formatted_address,
        "address_object": address_object,
        "used_country_hint": resolved_country_hint,
        "country_hint_source": country_hint_source,
        "can_create_without_client_address": False,
    }
