# Third-party dependecies
from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import validates
from sqlalchemy.orm import relationship

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.services.domain.item.item_states import ItemState as ItemStateEnum

class ItemState(db.Model, TeamScopedMixin):
    __tablename__ = "item_state"
    
    __table_args__ = (
        UniqueConstraint("team_id", "name", name="uq_itemstate_team_name"),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False, index=True)
    color = Column(String, nullable=False)
    default = Column(Boolean, default=False)
    description = Column(String)
    index = Column(Integer)

    entry_point =  Column(String) # open, completed, fail

    is_system = Column(Boolean, default=False, index=True)

    items = relationship(
        "Item",
        back_populates="item_state",
        lazy=True
    )

    team = relationship(
        "Team",
        backref="items_states",
        lazy=True
    )



    @validates("entry_point")
    def validate_entry_point(self, key, value):
        if value is None:
            return value

        if value not in ItemStateEnum._value2member_map_:
            raise ValueError(
                f"Invalid entry_point '{value}'. "
                f"Allowed values: {[e.value for e in ItemStateEnum]}"
            )
        return value
