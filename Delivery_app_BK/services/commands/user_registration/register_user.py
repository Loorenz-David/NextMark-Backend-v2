import random
import string

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ZoneVersion, db, Team, User, UserRole

from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields, build_create_result
from ..utils.client_id_generator import generate_client_id
from Delivery_app_BK.services.requests.common import (
    parse_optional_city_key,
    parse_optional_country_code,
)


def _generate_team_name(username: str) -> str:
    suffix = "".join(random.choices(string.digits, k=8))
    return f"{username} {suffix}"


def register_user(ctx: ServiceContext):
    ctx.inject_team_id = False
    relationship_map = {
        "team_id": Team,
        "team": Team,
        "user_role_id": UserRole,
    }
    ctx.set_relationship_map(relationship_map)


    field_set = extract_fields( ctx, return_single = True)

   
    username = field_set.get("username")
    email = field_set.get("email")
    password = field_set.get("password")
    phone_number = field_set.get("phone_number")
    time_zone = field_set.get("time_zone")
    default_country_code = parse_optional_country_code(
        field_set.get("default_country_code") or field_set.get("country_code"),
        field="default_country_code",
    )
    default_city_key = parse_optional_city_key(
        field_set.get("default_city_key") or field_set.get("city_key") or field_set.get("city"),
        field="default_city_key",
    )

    if not time_zone:
        time_zone = "UTC"
    
    if not username or not email or not password or phone_number is None:
        raise ValidationFailed(
            "Missing required fields: username, email, password, phone_number."
        )


    existing_user = (
        db.session.query(User)
        .filter((User.username == username) | (User.email == email))
        .first()
    )
    if existing_user:
        raise ValidationFailed("Username or email already exists.")

    team_name = _generate_team_name(username)
    
    user_fields = {
        "username": username,
        "email": email,
        "password": User().hash_password(password),
        "phone_number": phone_number,
        "user_role_id": 1, # Default role assignment
        "client_id": generate_client_id('user'),
    }

    user_instance: User = create_instance(ctx, User, user_fields)
    team_instance: Team = create_instance(
        ctx,
        Team,
        {
            "name": team_name,
            "time_zone": time_zone,
            "default_country_code": default_country_code,
            "default_city_key": default_city_key,
        },
    )
    user_instance.team = team_instance

   

    db.session.add(team_instance)
    db.session.add(user_instance)
    db.session.flush()

    if default_city_key and team_instance.id is not None:
        existing_initial_version = (
            db.session.query(ZoneVersion.id)
            .filter_by(
                team_id=team_instance.id,
                city_key=default_city_key,
                version_number=1,
            )
            .first()
        )
        if existing_initial_version is None:
            db.session.add(
                ZoneVersion(
                    team_id=team_instance.id,
                    city_key=default_city_key,
                    version_number=1,
                    is_active=False,
                )
            )

    user_instance.primals_team_id = team_instance.id
    user_instance.primals_role_id = user_instance.user_role_id
    user_instance.admin_app_current_workspace = "personal"
    user_instance.driver_app_current_workspace = "personal"
    user_results = build_create_result(ctx, [ user_instance ] )
    team_results = build_create_result(ctx, [ team_instance ] )
    db.session.commit()

    return {
        "user": user_results,
        "team": team_results,
    }
