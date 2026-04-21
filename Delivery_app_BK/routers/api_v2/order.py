from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from Delivery_app_BK.routers.utils.role_decorator import (
    role_required,
    ADMIN,
    ASSISTANT,
)
from Delivery_app_BK.routers.http.response import Response
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.run_service import run_service
from Delivery_app_BK.services.queries.order.list_orders import (
    list_orders as list_orders_service,
)
from Delivery_app_BK.services.queries.order.list_order_markers import (
    list_order_markers as list_order_markers_service,
)
from Delivery_app_BK.services.queries.order.get_order import (
    get_order as get_order_service,
)
from Delivery_app_BK.services.queries.order.get_order_route_context import (
    get_order_route_context as get_order_route_context_service,
)
from Delivery_app_BK.services.queries.order.get_order_event_history import (
    get_order_event_history as get_order_event_history_service,
)
from Delivery_app_BK.services.queries.order_states.list_order_states import (
    list_order_states as list_order_states_service,
)
from Delivery_app_BK.services.commands.order import (
    create_order as create_order_service,
    create_order_import as create_order_import_service
)
from Delivery_app_BK.services.commands.order.update_order import (
    update_order as update_order_service,
)
from Delivery_app_BK.services.commands.order.update_order_notes import (
    update_order_notes as update_order_notes_service,
)
from Delivery_app_BK.services.commands.order.delete_order import (
    delete_order as delete_order_service,
)
from Delivery_app_BK.services.commands.order.order_states.update_orders_state import (
    update_orders_state_payload as update_orders_state_service,
)
from Delivery_app_BK.services.queries.item.list_items import (
    list_items as list_items_service,
)
from Delivery_app_BK.services.commands.order.archive_order import (
    archive_order as archive_order_service
)
from Delivery_app_BK.services.commands.order.unarchive_order import (
    unarchive_order as unarchive_order_service
)


order_bp = Blueprint("api_v2_order_bp", __name__)


def _normalize_query_params():
    normalized = {}
    for raw_key, values in request.args.lists():
        key = raw_key[:-2] if raw_key.endswith("[]") else raw_key
        if not values:
            continue
        normalized[key] = values if len(values) > 1 else values[0]
    return normalized


@order_bp.route("/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_orders():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )
    
    outcome = run_service(lambda c: list_orders_service(c), ctx)

    response = Response()
   
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/map_markers/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_order_markers():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )

    outcome = run_service(lambda c: list_order_markers_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/states/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_order_states():
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )
    outcome = run_service(lambda c: list_order_states_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_order():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus = prevent_event_bus 
    )

    outcome = run_service(lambda c: create_order_service(c), ctx)
    response = Response()

    

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    
    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_order():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus = prevent_event_bus 
    )
    outcome = run_service(lambda c: update_order_service(c), ctx)
    response = Response()
    
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@order_bp.route("/notes/", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_order_notes():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_order_notes_service(c, "update"), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@order_bp.route("/notes/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_order_notes():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    outcome = run_service(lambda c: update_order_notes_service(c, "delete"), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@order_bp.route("/", methods=["DELETE"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def delete_order():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
    )
    
    outcome = run_service(lambda c: delete_order_service(c), ctx)
    response = Response()
  
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
   
    return response.build_successful_response(
        outcome.data or {},
        warnings=ctx.warnings,
    )


@order_bp.route("/<int:order_id>", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_order(order_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )
    outcome = run_service(lambda c: get_order_service(order_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/<int:order_id>/route-context", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_order_route_context(order_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )
    outcome = run_service(lambda c: get_order_route_context_service(order_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/<int:order_id>/events/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def get_order_event_history(order_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )
    outcome = run_service(lambda c: get_order_event_history_service(order_id, c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/<int:order_id>/items/", methods=["GET"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def list_order_items(order_id: int):
    identity = get_jwt()
    ctx = ServiceContext(
        query_params=_normalize_query_params(),
        identity=identity,
    )

    outcome = run_service(lambda c: list_items_service(c, order_id=order_id), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/<int:order_id>/state/<int:state_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def update_orders_state(order_id: int, state_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {} 
    prevent_event_bus = incoming_data.pop("prevent_event_bus", False)
    ctx = ServiceContext(
        identity=identity,
        incoming_data = incoming_data,
        prevent_event_bus = prevent_event_bus
    )
    outcome = run_service(
        lambda c: update_orders_state_service(c, order_id, state_id),
        ctx,
    )
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/import", methods=["PUT"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def create_order_import():
    identity = get_jwt()
    
    file = request.files.get('file')
    incoming_data = request.form.to_dict() if request.form else {}

    ctx = ServiceContext(
        incoming_file= file,
        incoming_data=incoming_data,
        query_params=request.args,
        identity=identity,
        extract_fields_key=False
    )

    outcome = run_service(lambda c: create_order_import_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        outcome.data,
        warnings=ctx.warnings,
    )


@order_bp.route("/archive", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def archive_order():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", True)
    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus = prevent_event_bus 
    )
    outcome = run_service(lambda c: archive_order_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )


@order_bp.route("/unarchive", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN, ASSISTANT])
def unarchive_order():
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    prevent_event_bus = incoming_data.pop("prevent_event_bus", True)

    ctx = ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus=prevent_event_bus,
    )

    outcome = run_service(lambda c: unarchive_order_service(c), ctx)
    response = Response()

    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)

    return response.build_successful_response(
        {},
        warnings=ctx.warnings,
    )
