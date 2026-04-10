from sqlalchemy.orm import object_session
from sqlalchemy.inspection import inspect
from flask_sqlalchemy.model import Model
from Delivery_app_BK.models import db
from Delivery_app_BK.errors import ValidationFailed
from .column_inspector import ColumnInspector



class InstanceLinker:

    '''
    assumes owner and related are already SQLAlchemy instances
    '''
    def __init__( self, owner, related ) -> bool:
        self.owner = owner
        self.related = related

        if object_session(self.owner) is None:
            db.session.add(self.owner)

        if object_session(self.related) is None:
            db.session.add(self.related)

        self.owner_model:Model = inspect( owner ).mapper.class_
        self.related_model:Model = inspect( related ).mapper.class_

    
    def link_using_foreign_key(self,column):

        if not isinstance(column, ColumnInspector):
            column = ColumnInspector(column, self.owner_model)

        if not column.is_related_to_model(self.related_model.__tablename__):
            raise ValidationFailed(
                    f"Model {self.owner_model.__name__} has no FK relationship "
                    f"to '{self.related_model.__tablename__}' through column "
                    f"'{column.column_name}'."
            )
        
        setattr(self.owner, column.column_name, self.related.id)

        return True
    
    def link_using_relationship(self,column):
        if not isinstance(column, ColumnInspector):
            column = ColumnInspector(column, self.owner_model)
      
        if not column.is_relationship():
            raise ValidationFailed(
                f"'{column.column_name}' is not a valid relationship on {self.owner_model.__name__}"
            )

        if column.relationship.uselist:
            raise ValidationFailed(
                "Collection relationships must be assigned as a full list"
            )

        # One-to-one or many-to-one (uselist=False)
        setattr(self.owner, column.column_name, self.related)

        return True
