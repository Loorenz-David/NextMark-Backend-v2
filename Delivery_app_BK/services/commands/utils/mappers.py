from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext


def build_dynamic_ids_map(
    instances: list,
    target_key: str = "client_id",
    extract_key: str = "id",
    extract_fields: list | None = None,
    ctx: ServiceContext | None = None,
) -> dict:
    if not isinstance(instances, list):
        raise ValidationFailed("Instances must be provided as a list.")

    object_map: dict = {"ids_without_match": []}

    for instance in instances:
        if not hasattr(instance, extract_key):
            if ctx is not None:
                ctx.set_warning(
                    f"Instance does not have the attribute '{extract_key}'."
                )
                continue
            raise ValidationFailed(
                f"Instance does not have the attribute '{extract_key}'."
            )
        extract_value = getattr(instance, extract_key)

        if not hasattr(instance, target_key):
            if ctx is not None:
                ctx.set_warning(
                    f"Instance does not have the attribute '{target_key}'."
                )
            object_map["ids_without_match"].append(extract_value)
            continue

        target_value = getattr(instance, target_key)
        if target_value is None:
            if ctx is not None:
                ctx.set_warning(
                    f"Instance attribute '{target_key}' is None for id '{extract_value}'."
                )
            object_map["ids_without_match"].append(extract_value)
            continue

        if extract_fields:
            data = {target_key: target_value}
            for field in extract_fields:
                if not hasattr(instance, field):
                    if ctx is not None:
                        ctx.set_warning(
                            f"Instance does not have the attribute '{field}'."
                        )
                        data[field] = None
                        continue
                    raise ValidationFailed(
                        f"Instance does not have the attribute '{field}'."
                    )
                data[field] = getattr(instance, field)
            object_map[target_value] = data
        else:
            object_map[target_value] = extract_value

    return object_map
