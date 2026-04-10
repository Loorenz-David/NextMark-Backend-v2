import json


def parsed_string_to_list(s, ctx):
 

    # Case 1: Already a list
    if isinstance(s, (list, tuple)):
        return list(s)

    # Case 2: String input
    if isinstance(s, str):
        s = s.strip()

        # Try parsing as JSON first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fallback: comma-separated string
        return [col.strip() for col in s.split(",") if col.strip()]

    # Invalid input
    ctx.set_warning(
        'Parameter "s" must be a JSON array or comma separated string: column_1,column_2'
    )
    return []


def str_to_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y")

    return bool(value)