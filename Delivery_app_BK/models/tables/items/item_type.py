from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from Delivery_app_BK.models import db

# Local application imports
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


type_property_association = db.Table(
    "type_property_association",
    Column("type_id", Integer, ForeignKey("item_type.id", ondelete="CASCADE"), primary_key=True),
    Column("property_id", Integer, ForeignKey("item_property.id", ondelete="CASCADE"), primary_key=True)
)


class ItemType(db.Model, TeamScopedMixin):
    __tablename__ = "item_type"
    __table_args__ = (
        UniqueConstraint("team_id", "name", name="uq_itemtype_team_name"),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False, index=True)
    is_system = Column(Boolean, default=False, index=True)
    
   

    properties = db.relationship(
        "ItemProperty",
        secondary=type_property_association,
        back_populates="item_types"
    )

    team = relationship(
        "Team",
        backref="item_types",
        lazy=True
    )
