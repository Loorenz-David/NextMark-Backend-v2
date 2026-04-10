# Thirs-party dependencies
from sqlalchemy.orm import validates
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy import UniqueConstraint

# Local application imports
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


from Delivery_app_BK.services.domain.order.order_events import OrderEventPrintDocuments
from Delivery_app_BK.services.domain.item.item_events import itemEventPrintDocuments
from Delivery_app_BK.services.domain.route_operations.plan.plan_events import planEventPrintDocuments

class LabelTemplate(db.Model, TeamScopedMixin):
    __tablename__ = "label_template"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "event",
            "channel",
            name="uq_label_template_team_event_channel"
        ),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    enable = Column( Boolean, default=False )
    channel = Column(String)  # Front end accepts "items" or "order"
    selected_variant = Column(String)
    orientation = Column(String)
    event = Column(String)
    ask_permission = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False, index=True)
    
    team = relationship(
        "Team",
        backref="print_template_lable",
        lazy=True
    )

    ALLOWED_CHANNELS = set(["item","order","route"])
    @validates("channel")
    def validate_channel(self, key, value):
        if value not in self.ALLOWED_CHANNELS:
            raise ValidationFailed(
                f"Invalid channel '{value}'. "
                f"Allowed values: {self.ALLOWED_CHANNELS}"
            )
        return value
    
    ALLOWED_VARIANTS = set(["classic","7cm - 10cm"])
    @validates("selected_variant")
    def validate_channel(self, key, value):
        if value not in self.ALLOWED_VARIANTS:
            raise ValidationFailed(
                f"Invalid channel '{value}'. "
                f"Allowed values: {self.ALLOWED_VARIANTS}"
            )
        return value
    
    ALLOWED_ORIENTATIONS = set(['horizontal','vertical'])
    @validates('orientation')
    def validate_orientation(self,key,value):
        if value not in self.ALLOWED_ORIENTATIONS:
             raise ValidationFailed(
                f"Invalid channel '{value}'. "
                f"Allowed values: {self.ALLOWED_VARIANTS}"
            )
        return value
    
    
    @validates("event")
    def validate_event(self, key, value):
        if (value not in OrderEventPrintDocuments._value2member_map_ and value not in itemEventPrintDocuments._value2member_map_  and value not in planEventPrintDocuments._value2member_map_):
            raise ValidationFailed(
                f"Invalid event '{value}'. "
                f"Allowed events: {[e.value for e in OrderEventPrintDocuments]} and {[e.value for e in itemEventPrintDocuments]} "
            )
        return value

