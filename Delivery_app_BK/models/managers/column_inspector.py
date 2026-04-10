from sqlalchemy.inspection import inspect
from sqlalchemy import Column
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import UnmappedInstanceError
from sqlalchemy.exc import NoInspectionAvailable
from Delivery_app_BK.errors import NotFound, ValidationFailed
from datetime import datetime, timezone

class ColumnInspector:

    def __init__(self, column, model):
        self.model = None
        self.mapper = None
        self.column = None
        self.column_name = None
        self.column_type = None
        self.relationship_prop = None
        self.relationship = None
        self.foreign_key = None

        if self.is_sqlalchemy_instance(model):
            self.model = model
            self.mapper = inspect(model)
        else:
            raise ValidationFailed(
                f"Model '{model.__name__}' is not a valid SQLAlchemy instance."
            )

       
        if self.is_sqlalchemy_column(column):
            self.column = column
            self.column_name = column.key

            # if the column is not a Column instance then it must be a string.
        else:
            if not isinstance(column, str):
                raise ValidationFailed(
                    f"Column '{column}' must be a string or a SQLAlchemy Column instance."
                )

            self.column_name = column

            # if the given column is a relationship it will get it and skipped the assignment to self.column
            self.relationship = self.get_relationship()

            if not self.is_relationship():
                self.column = self.get_column_instance()
                self.column_type = self.get_python_type()
            else:
                self.column_type = None

    
    # checks if the column holds any foreign keys
    def is_foreign_key(self):
        if self.column is None or not self.column.foreign_keys:
            return False
        self.foreign_key = next(iter(self.column.foreign_keys))
        return bool(self.column.foreign_keys)

    def is_relationship(self):
        if self.relationship:
            return True
        
        return False

    # chek if the given model holds the relationship to the column
    def is_related_to_model(self,name_of_model_to_check):

        if not self.is_foreign_key():
            return False
        
        # gets the first foreign key
        foreign_key = list(self.column.foreign_keys)[0]
        target_model = foreign_key.column.table

        return target_model.name == name_of_model_to_check

    # obtains the Column object from the model
    def get_column_instance(self):
        mapper = self.mapper 
        column_name = self.column_name
        column = mapper.columns.get( column_name, None )
        if column is not None:
            return column
        
        raise NotFound(
            f"Column '{column_name}' not found in model '{self.model.__tablename__}'."
        )

    def get_relationship(self):
        return self.mapper.relationships.get(self.column_name)

    def get_column_type(self):
        return self.column.type
    
    def get_python_type(self):
        try:
            
            return self.column.type.python_type
        except NotImplementedError:
            return object

    def validate_injection(self, value):
        if not self.column_type:
            raise ValidationFailed(
                "Unable to validate value because the column type is missing."
            )

        if self.is_relationship():
            raise ValidationFailed(
                f"'{self.column_name}' is a relationship and cannot be set directly."
            )

        if value is None:
            return None

        # use for JSONB and JSON columns as the type is read as dict in python
   
        if self.column_type is dict:
            if isinstance(value, (dict, list)):
                return value

            raise ValidationFailed(
                f"Invalid value for '{self.column_name}'. Expected a JSON object."
            )

        if self.column_type is datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:

                    # Handles both Python and JS ISO formats
                    date = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

                    return date
                except ValueError:
                    raise ValidationFailed(
                        f"Invalid datetime format for '{self.column_name}'."
                    )
            raise ValidationFailed(
                f"Invalid value for '{self.column_name}'. Expected a datetime."
            )

        if self.column_type is bool:
            if type(value) is bool:
                return value
            raise ValidationFailed(
                f"Invalid value for '{self.column_name}'. Expected a boolean."
            )

        if self.column_type is int:
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            raise ValidationFailed(
                f"Invalid value for '{self.column_name}'. Expected an integer."
            )

        if self.column_type is float:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            raise ValidationFailed(
                f"Invalid value for '{self.column_name}'. Expected a number."
            )

        if self.column_type is str:
            if isinstance(value, str):
                return value
            raise ValidationFailed(
                f"Invalid value for '{self.column_name}'. Expected a string."
            )

        if self.column_type is object:
            return value

        if isinstance(value, self.column_type):
            return value

        expected = getattr(self.column_type, "__name__", str(self.column_type))
        received = getattr(type(value), "__name__", str(type(value)))
        raise ValidationFailed(
            f"Invalid value for '{self.column_name}'. Expected '{expected}', got '{received}'."
        )

    def get_related_model( self ):

        if self.is_relationship():
            return self.relationship.mapper.class_
        elif self.is_foreign_key():
            # SQLAlchemy 2 no longer exposes ``table.mapper``.
            # Resolve the target model through this model's mapped relationships.
            for relationship in self.mapper.relationships:
                local_columns = relationship.local_columns or set()
                if self.column in local_columns:
                    return relationship.mapper.class_

            # Fallback: try matching by referenced table name when direct local
            # column mapping is not available (defensive for custom mappings).
            target_table_name = self.foreign_key.column.table.name
            for relationship in self.mapper.relationships:
                if relationship.mapper.persist_selectable.name == target_table_name:
                    return relationship.mapper.class_
            return None
        
        return None

    @staticmethod
    def is_sqlalchemy_instance(obj):
        try:
            inspect(obj)
            return True
        except (UnmappedInstanceError, NoInspectionAvailable):
            return False

    @staticmethod
    def is_sqlalchemy_column(obj):
        return isinstance(obj, (Column, InstrumentedAttribute))
