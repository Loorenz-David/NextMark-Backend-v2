# Third-party dependencies
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class CostumerAddress(db.Model, TeamScopedMixin):
    __tablename__ = "costumer_address"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True, nullable=True)
    costumer_id = Column(
        Integer,
        ForeignKey("costumer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = Column(String, nullable=True)
    address = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    costumer = relationship(
        "Costumer",
        back_populates="addresses",
        foreign_keys=[costumer_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_costumer_address_address_gin", "address", postgresql_using="gin"),
    )
