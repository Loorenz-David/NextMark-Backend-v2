from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db


class OrderScalarCounter(db.Model):
    __tablename__ = "order_scalar_counter"

    id = Column(Integer, primary_key=True)
    team_id = Column(
        Integer,
        ForeignKey("team.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    next_value = Column(Integer, nullable=False, default=1000)

    team = relationship("Team", backref="order_scalar_counter")
