from typing import List, Dict

from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext


def build_ids_map ( 
        unpacked_instances: List[ Dict ] , 
        ctx:ServiceContext,
        table:str = "",
        
):

    object_map = {}

    for obj in unpacked_instances:

        target_id = obj.get('id')
        if not target_id:
            raise ValidationFailed(f"when building ids map for intance { table }, the object 'id' was missing.")

        object_map[ target_id ] = obj

    

    return object_map


def build_client_ids_map( 
    unpacked_instances: List[ Dict ] , 
    ctx:ServiceContext,
    table:str = "",
):
    object_map = {}
    all_ids = []
    
    for obj in unpacked_instances:
        target_id = obj.get('client_id')
        if target_id is None or target_id == "":
            target_id = obj.get("id", None)

        if target_id is None or target_id == "":
            raise ValidationFailed(f"when building ids map for intance { table }, the object 'id' was missing.")

        target_id = str( target_id )

        object_map[ target_id ] = obj
        all_ids.append( target_id )

    

    return { "byClientId": object_map, "allIds": all_ids } 