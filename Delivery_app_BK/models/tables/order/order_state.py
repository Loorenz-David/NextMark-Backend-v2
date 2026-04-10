
from marshmallow import validates
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

# Local application imports
from Delivery_app_BK.errors.validation import ValidationFailed
from Delivery_app_BK.models.tables.order.order_event import OrderEvent
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.services.domain.order.order_states import OrderState as OrderStateEnum


"""
current static plans:
- Draft ( the order is created )
- Confirmed ( the order is confirmed, )
- Preparing ( the order is getting prepared )
- Ready ( the order is ready to be delivered or picked up )
- Processing ( the order is in progress of being deliver )
- Completed ( the order is completed )
- Cancelled ( the order is cancelled )
- Fail ( the order is failed )

the user will be able to create more in between


"""

# client_id supports optimistic updates from the front end.
class OrderState (db.Model, TeamScopedMixin):
    __tablename__ = "order_state"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, index=True)
    index = Column( Integer )
    color = Column(String)

    is_system = Column(Boolean, default=False, index=True)

    order = relationship(
        "Order",
        back_populates = "state"
    )

    order_state_transition_rules = relationship(
        "OrderStateTransitionRule",
        back_populates = "allowed_state"
    )

    team = relationship(
        "Team",
        backref="route_states",
        lazy=True
    )

    @validates("name")
    def validate_name(self, key, value):
        if not value:
            raise ValidationFailed("OrderState name cannot be empty.")
        if value not in OrderStateEnum._value2member_map_:
            raise ValidationFailed(
                f"Invalid OrderState name '{value}'. "
                f"Allowed values: {[e.value for e in OrderStateEnum]}"
            )
        return value
    


