from typing import Type
from flask_sqlalchemy.model import Model

from Delivery_app_BK.models import db
from Delivery_app_BK.models.managers.column_inspector import ColumnInspector
from Delivery_app_BK.models.managers.instance_linker import InstanceLinker
from Delivery_app_BK.errors import ValidationFailed, NotFound

from ...context import ServiceContext
from ...queries.get_instances import get_instances
from ...queries.get_instance import get_instance


"""
Relationship injection rules:

- Scalar relationships (one-to-one, many-to-one):
  Assigned directly.

- Collection relationships (one-to-many, many-to-many):
  MUST be provided as a full list.
  Missing items are removed automatically.

- All relationship queries are scoped by team_id.
"""

def inject_fields( 
        ctx: ServiceContext,
        instance: Type[ Model ],
        fields: dict,

) -> Type[ Model ]:
    
    if instance is None:
        raise ValidationFailed("instace is required to inject fields to an instance.")
    if fields is None:
        raise ValidationFailed("Fields are required to inject data to an instance.")
    
    Model = instance.__class__

    with db.session.no_autoflush:
        for field, value in fields.items():
         
            if ctx.skip_id_instance_injection:
                if field == 'id':
                    ctx.set_warning(f'The provided id was ignore because the current context does not allow ID injection')
                    continue
            
            column_inspector = ColumnInspector( field, Model )

          
            # if the column holds a foreign key, it will link using the foreign key
            if column_inspector.is_foreign_key():
               
                related_model = (
                    ctx.relationship_map.get( column_inspector.column_name )
                    or column_inspector.get_related_model()
                    )
                
                if related_model is None:
                    raise ValidationFailed(
                        f"Missing relationship mapping for '{column_inspector.column_name}'."
                    )
                if  not value:
                    continue 
                
                related = get_instance( 
                    ctx = ctx,
                    model = related_model,
                    value = value 
                )

                if related is None:
                    raise NotFound(
                        f"Related record for '{column_inspector.column_name}' was not found."
                    )
                
                link = InstanceLinker(
                    owner = instance,
                    related = related,
                ).link_using_foreign_key( column_inspector )
                if not link:
                    raise ValidationFailed(
                        f"Unable to assign '{column_inspector.column_name}' with the provided value."
                    )

                continue
            
            # if the column is a relationship, it will link using relationship_props
            elif column_inspector.is_relationship():
                related_model = (
                    ctx.relationship_map.get( column_inspector.column_name )
                    or column_inspector.get_related_model()
                    )
                if related_model is None:
                    raise ValidationFailed(
                        f"Missing relationship mapping for '{column_inspector.column_name}'."
                    )

                if column_inspector.relationship.uselist:
                    if not isinstance(value, list):
                        raise ValidationFailed(
                            f"'{column_inspector.column_name}' must be provided as a list."
                        )
                    if not value:
                        setattr(instance, column_inspector.column_name, [])
                        continue

                    related_instances = get_instances(
                        ctx = ctx,
                        model = related_model,
                        ids = value
                    )
                    setattr(instance, column_inspector.column_name, related_instances)
                    continue

                if value is None:
                    setattr(instance, column_inspector.column_name, None)
                    continue

                if isinstance(value, list):
                    raise ValidationFailed(
                        f"'{column_inspector.column_name}' must be a single id."
                    )

                # one-to-one or many-to-one
                related = get_instance( 
                    ctx = ctx,
                    model = related_model,
                    value = value,
                )
                if related is None:
                    raise NotFound(
                        f"Related record for '{column_inspector.column_name}' was not found."
                    )
                link = InstanceLinker(
                        owner = instance,
                        related = related,
                    ).link_using_relationship( column_inspector )
                if not link:
                    raise ValidationFailed(
                        f"Unable to link '{column_inspector.column_name}' with the provided value."
                    )
                continue




            valid_value = column_inspector.validate_injection( value )

            setattr(instance, column_inspector.column_name, valid_value)

        
    return instance 
