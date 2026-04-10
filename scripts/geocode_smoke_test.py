from __future__ import annotations

import argparse
import json
import sys

from Delivery_app_BK.geocoding.orchestrator import geocode_address


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the active geocoding provider.")
    parser.add_argument("query", help="Free-text address query to geocode.")
    parser.add_argument(
        "--country-hint",
        dest="country_hint",
        help="Optional ISO 3166-1 alpha-2 country code, e.g. SE.",
    )
    args = parser.parse_args()

    result = geocode_address(args.query, country_hint=args.country_hint)
    if result is None:
        print(json.dumps({"found": False, "query": args.query}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "found": True,
                "formatted_address": result.formatted_address,
                "address_object": result.to_address_dict(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())