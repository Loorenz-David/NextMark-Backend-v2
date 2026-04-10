import csv
from io import TextIOWrapper
from werkzeug.datastructures import FileStorage
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.utils import generate_client_id
from ...context import ServiceContext
from . import create_order
"""

FileStorage
├── filename        → "orders.csv"
├── content_type    → "text/csv"
├── stream          → binary file stream
├── read()          → bytes
├── save(path)      → save to disk

"""

def _validate_columns( reader ):
    required_columns = {
        "external_order_id",
        "client_first_name",
        "client_email",
    }

    missing = required_columns - set(reader.fieldnames)

    if missing:
        raise ValidationFailed(f"Missing columns: {', '.join(missing)}")
    
def _validate_file( file:FileStorage, ctx ):

    if not file:
        raise ValidationFailed("No file provided")

    if not file.filename.lower().endswith(".csv"):
        raise ValidationFailed("Only CSV files are allowed")
    
    if file.content_type not in ("text/csv", "application/vnd.ms-excel"):
        ctx.set_warning("Unexpected content-type for CSV file")

def _order_import_mapper(row):
    phone_number = _clean_value(row.get("phone_number"))
    phone_obj = _build_phone_object(phone_number)
    address_obj = _build_address_object(row)

    map_order = {
        "client_id": generate_client_id('order_import_'),
        "external_order_id": _clean_value(row.get("external_order_id")),
        "external_source":_clean_value(row.get("external_source")) or 'csv_import',
        "reference_number": _clean_value(row.get("order_reference_number")),
        "external_tracking_number": _clean_value(row.get("tracking_number")),
        "external_tracking_link": _clean_value(row.get("tracking_link")),
        "client_first_name": _clean_value(row.get("client_first_name")),
        "client_last_name": _clean_value(row.get("client_last_name")),
        "client_email": _clean_value(row.get("client_email")),
    }

    if phone_obj:
        map_order["client_primary_phone"] = phone_obj

    if address_obj:
        map_order["client_address"] = address_obj

    return map_order

def _item_import_mapper(row):

    map_item = {
        "client_id": generate_client_id('order'),
        "article_number": _clean_value(row.get("article_number")),
        "reference_number": _clean_value(row.get("item_reference_number")),
        "item_type": _clean_value(row.get("item_type")),
        "page_link": _clean_value(row.get("page_link")),
        "quantity": _parse_int(row.get("quantity"), default=1),
        "weight": _parse_int(row.get("weight")),
        "dimension_width": _parse_int(row.get("dimension_width")),
        "dimension_depth": _parse_int(row.get("dimension_depth")),
        "dimension_height": _parse_int(row.get("dimension_height")),
    }

    return {key: value for key, value in map_item.items() if value is not None}

def _clean_value(value):
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None

def _parse_int(value, default=None):
    cleaned = _clean_value(value)
    if cleaned is None:
        return default
    try:
        return int(cleaned)
    except ValueError:
        try:
            return int(float(cleaned))
        except ValueError:
            return default

def _parse_float(value):
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None

def _build_phone_object(phone):
    if not phone:
        return None
    phone_number = phone.lstrip("+").strip()
    if not phone_number:
        return None
    return {
        "prefix": "+",
        "number": phone_number,
    }

def _build_address_object(row):
    street_address = _clean_value(row.get("street_address"))
    postal_code = _clean_value(row.get("postal_code"))
    city = _clean_value(row.get("city")) or ''
    country = _clean_value(row.get("country")) 
    lat = _parse_float(row.get("lat"))
    lng = _parse_float(row.get("lng"))
  
    if any(value is None for value in [street_address, postal_code, country, lat, lng]):

        return None

    return {
        "street_address": street_address,
        "postal_code": postal_code,
        "city": city,
        "country": country,
        "coordinates": {
            "lat": lat,
            "lng": lng,
        },
    }

def _build_order_group_key(row):
    order_key_fields = [
        "external_order_id",
        "order_reference_number",
        "delivery_plan_id",
        "external_source",
        "tracking_number",
        "client_first_name",
        "client_last_name",
        "client_email",
        "phone_number",
        "street_address",
        "postal_code",
        "city",
        "country",
        "lat",
        "lng",
    ]
    return tuple(_clean_value(row.get(field)) for field in order_key_fields)

def create_order_import( ctx:ServiceContext  ):
    file:FileStorage = ctx.incoming_file
    delivery_plan_id = None

    if ctx.query_params:
        delivery_plan_id = ctx.query_params.get("delivery_plan_id")

    if not delivery_plan_id and ctx.incoming_data:
        delivery_plan_id = ctx.incoming_data.get("delivery_plan_id")

    if delivery_plan_id is not None:
        delivery_plan_id = str(delivery_plan_id).strip() or None

    _validate_file(file, ctx)

    stream = TextIOWrapper(file.stream, encoding="utf-8", newline="")
    reader = csv.DictReader(stream)

    _validate_columns(reader)

    orders = []
    current_order = None
    last_order_key = None

    for index, row in enumerate(reader, start=2):
        try:
            group_row = dict(row)
            order_key = _build_order_group_key(group_row)

            if order_key != last_order_key:
                current_order = _order_import_mapper(row)
                if delivery_plan_id:
                    parsed_plan_id = _parse_int(delivery_plan_id)
                    if parsed_plan_id is not None:
                        current_order["delivery_plan_id"] = parsed_plan_id
                current_order["items"] = []
                orders.append(current_order)
                last_order_key = order_key

            item_obj = _item_import_mapper(row)
            if item_obj and current_order is not None:
                current_order["items"].append(item_obj)
        except Exception as e:
            ctx.set_warning(f"Row {index}: {str(e)}")

    ctx.incoming_data = orders
    result = create_order(ctx)

    return result
        


    
