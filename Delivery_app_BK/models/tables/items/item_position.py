# Third-party dependecies
from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class ItemPosition(db.Model, TeamScopedMixin):
    __tablename__ = "item_position"
    __table_args__ = (
        UniqueConstraint("team_id", "name", name="uq_itemposition_team_name"),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False, index=True)
    default = Column(Boolean, nullable=False)
    description = Column(String, nullable=False)

    is_system = Column(Boolean, default=False, index=True)

    team = relationship(
        "Team",
        backref="item_positions",
        lazy=True
    )
