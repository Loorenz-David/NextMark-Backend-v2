#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

DRIVER_ID_VALUE="${DRIVER_ID:-}"
START_FACILITY_ID_VALUE="${START_FACILITY_ID:-}"
END_FACILITY_ID_VALUE="${END_FACILITY_ID:-}"

jq \
  --arg key "$SECRET_KEY" \
  --arg driver_id "$DRIVER_ID_VALUE" \
  --arg start_facility_id "$START_FACILITY_ID_VALUE" \
  --arg end_facility_id "$END_FACILITY_ID_VALUE" \
  '. + {
    key: $key,
    team_id: 1,
    user_id: 1,
    time_zone: "Europe/Stockholm",
    default_country_code: "SE"
  }
  | .route_plan |= map(
      if (.route_group_defaults.route_solution | type) == "object" then
        .route_group_defaults.route_solution |= (
          if $driver_id != "" then
            . + { driver_id: ($driver_id | tonumber) }
          else
            del(.driver_id)
          end
          | if $start_facility_id != "" then
              . + { start_facility_id: ($start_facility_id | tonumber) }
            else
              del(.start_facility_id)
            end
          | if $end_facility_id != "" then
              . + { end_facility_id: ($end_facility_id | tonumber) }
            else
              del(.end_facility_id)
            end
        )
      else
        .
      end
    )' \
  "$SCRIPT_DIR/future_delivery_simulation_seed.json" \
| curl -X POST http://0.0.0.0:5050/api_v2/seed/test-data \
  -H "Content-Type: application/json" \
  -d @-