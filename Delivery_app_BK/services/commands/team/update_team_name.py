

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import Team, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.requests.common import parse_optional_country_code


def update_team_name(ctx: ServiceContext):
    if not ctx.team_id:
        raise ValidationFailed("Team id is required to update team name.")

    incoming_data = ctx.incoming_data or {}
    raw_name = incoming_data.get("name") or incoming_data.get("team_name")
    default_country_code = parse_optional_country_code(
        incoming_data.get("default_country_code"),
        field="default_country_code",
    )

    if raw_name is None and default_country_code is None:
        raise ValidationFailed("Either team name or default_country_code is required to update team settings.")

    name = None
    if raw_name is not None:
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValidationFailed("Team name is required to update team name.")
        name = raw_name.strip()

    team: Team = get_instance(ctx=ctx, model=Team, value=ctx.team_id)
    if name is not None:
        team.name = name
    if "default_country_code" in incoming_data:
        team.default_country_code = default_country_code
    db.session.commit()
    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "default_country_code": team.default_country_code,
        }
    }
