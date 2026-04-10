from __future__ import annotations
from typing import Any, Dict, Optional
from sqlalchemy.inspection import inspect

from Delivery_app_BK.errors import PermissionDenied, ValidationFailed

from ..context import ServiceContext



def instance_has_column(instance, column_name: str) -> bool:
    return column_name in inspect(instance.__class__).columns

def require_team_id(ctx: ServiceContext) -> int:
   
    team_id = ctx.team_id
    if team_id is None:
        raise PermissionDenied("User is not assigned to a team")
    return team_id


def ensure_instance_in_team(instance: Any, ctx: ServiceContext) -> None:

    if not hasattr(instance, "team_id"):
        return
    team_id = require_team_id(ctx)
    
    if instance.team_id != team_id:
        raise PermissionDenied("You are not authorized to access this resource")


def model_requires_team(Model: Any) -> bool:
    return hasattr(Model, "team_id")


def inject_team_id(fields: Dict[str, Any], ctx: ServiceContext) -> Dict[str, Any]:
    if not hasattr(fields, "items"):
        raise ValidationFailed("Fields must be provided as a dictionary")

    fields = dict(fields)

    
    if "team_id" not in fields:
        fields["team_id"] = require_team_id(ctx)

    return fields

def is_system_default(obj: Any) -> bool:
    if instance_has_column( obj, 'is_system' ):
        if getattr(obj, 'is_system'):
            return True

    return False


