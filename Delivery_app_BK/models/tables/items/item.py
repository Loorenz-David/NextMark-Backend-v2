# Third-party dependecies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship, validates
from Delivery_app_BK.models import db

# Local application imports
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class Item(db.Model, TeamScopedMixin):
    __tablename__ = "item"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    
    article_number = Column(String, nullable=False, index=True)
    reference_number = Column(String, index=True)
    
    item_type = Column(String)

    is_system = Column(Boolean, default=False, index=True)
    
    properties = Column(JSONB().with_variant(JSON, "sqlite"))  # a list of dicts imprinted by the table ItemProperties


    quantity = Column(Integer)

    order_id = Column(
        Integer,
        ForeignKey("order.id", ondelete="CASCADE")
    )

    item_position = Column(String, nullable=True, index=True)

    item_state_id = Column(
        Integer,
        ForeignKey("item_state.id")
    )
    # Access through relationship links

    order = relationship(
        "Order",
        back_populates = "items"
    )

    item_state = relationship(
        "ItemState",
        back_populates="items"
    )

    order = relationship(
        "Order",
        back_populates="items"
    )

    team = relationship(
        "Team",
        backref="items",
    )

    # link to an extrnal page...
    page_link = Column(String)
    item_images = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True, default=list)

    # moving dimensions to:
    dimension_depth = Column(Integer) #cm
    dimension_height = Column(Integer) #cm
    dimension_width = Column(Integer) #cm
    weight = Column(Integer) # grams

    @validates("item_images")
    def validate_item_images(self, key, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("item_images must be a list of strings.")
        for index, image_url in enumerate(value):
            if not isinstance(image_url, str):
                raise ValueError(f"item_images[{index}] must be a string.")
        return value
   
    def __repr__(self):
        return f"<Item {self.article_number}>"
