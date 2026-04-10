from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext


def extract_fields(ctx: ServiceContext, return_single = False) -> list[dict]:
    incoming = ctx.incoming_data or {}
    if ctx.extract_fields_key == False:
        return [incoming] if isinstance(incoming, dict) else incoming

    if "fields" not in incoming:
        raise ValidationFailed("Missing key 'fields' in request payload.")

    fields = incoming.get("fields")
    if isinstance(fields, dict):
        if return_single:
            return fields
        else:
            return [fields]
    if isinstance(fields, list) and all(isinstance(item, dict) for item in fields):
        if not fields:
            raise ValidationFailed("No fields provided to create instances.")
        
        if return_single:
            fields[0]
        else:
            return fields

    raise ValidationFailed("'fields' must be a dictionary or a list of dictionaries.")


def extract_ids(ctx: ServiceContext) -> list[int]:
    incoming = ctx.incoming_data or {}
    if "target_id" in incoming:
        target = incoming.get("target_id")
    elif "target_ids" in incoming:
        target = incoming.get("target_ids")
    else:
        raise ValidationFailed("Missing 'target_id' or 'target_ids' in request payload.")

    if isinstance(target, int) or isinstance( target, str ) and not isinstance(target, bool):
        return [target]
    if isinstance(target, list):
        if not target:
            raise ValidationFailed("No target ids provided for deletion.")
        if all( isinstance(item, int) or isinstance( item, str ) and not isinstance(item, bool) for item in target ):
            return target
        raise ValidationFailed("'target_ids' must be a list of integers.")

    raise ValidationFailed("'target_id' must be an integer or 'target_ids' a list of integers.")


def extract_targets(ctx: ServiceContext) -> list[dict]:
    incoming = ctx.incoming_data or {}
    if "target" in incoming:
        targets = incoming.get("target")
    elif "targets" in incoming:
        targets = incoming.get("targets")
    else:
        raise ValidationFailed("Missing 'target' or 'targets' in request payload.")

    if isinstance(targets, dict):
        targets_list = [targets]
    elif isinstance(targets, list) and all(isinstance(item, dict) for item in targets):
        if not targets:
            raise ValidationFailed("No targets provided for update.")
        targets_list = targets
    else:
        raise ValidationFailed("'target' must be a dictionary or 'targets' a list of dictionaries.")

    normalized = []
    for target in targets_list:

        if "target_id" not in target or "fields" not in target:
            raise ValidationFailed("Each target must include 'target_id' and 'fields'.")
        target_id = target.get("target_id")
        fields = target.get("fields")

        if not isinstance(target_id, (int, str))  :
            raise ValidationFailed("'target_id' must be an integer. or string. ")
        if not isinstance(fields, dict):
            raise ValidationFailed("'fields' must be a dictionary.")
        normalized.append({"target_id": target_id, "fields": fields})

    return normalized
