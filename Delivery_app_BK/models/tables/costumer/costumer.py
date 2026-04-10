# Third-party dependencies
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class Costumer(db.Model, TeamScopedMixin):
    __tablename__ = "costumer"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True, nullable=True)
    first_name = Column(String, nullable=False, index=True)
    last_name = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    external_source = Column(String, nullable=True, index=True)
    external_costumer_id = Column(String, nullable=True, index=True)

    default_address_id = Column(
        Integer,
        ForeignKey("costumer_address.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_primary_phone_id = Column(
        Integer,
        ForeignKey("costumer_phone.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_secondary_phone_id = Column(
        Integer,
        ForeignKey("costumer_phone.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    addresses = relationship(
        "CostumerAddress",
        back_populates="costumer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        foreign_keys="CostumerAddress.costumer_id",
    )

    phones = relationship(
        "CostumerPhone",
        back_populates="costumer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        foreign_keys="CostumerPhone.costumer_id",
    )

    operating_hours = relationship(
        "CostumerOperatingHours",
        back_populates="costumer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        foreign_keys="CostumerOperatingHours.costumer_id",
    )

    orders = relationship(
        "Order",
        back_populates="costumer",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_costumer_team_id_email", "team_id", "email"),
        Index("ix_costumer_team_id_last_name", "team_id", "last_name"),
    )
