from typing import TypeVar

# Third-party dependencies
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()



from .tables.users.user import User
from .tables.role.user_role import UserRole
from .tables.role.base_role import BaseRole
from .tables.role.role_rules.date_range_access_rule import DateRangeAccessRule
from .tables.role.role_rules.order_state_transiton_rule import OrderStateTransitionRule
from .tables.team.team import Team
from .tables.team.invitation import TeamInvites

from .tables.infrastructure.facility import Facility
from .tables.infrastructure.vehicle import Vehicle
from .tables.items.item import Item
from .tables.items.item_type import ItemType
from .tables.items.item_property import ItemProperty
from .tables.items.item_state import ItemState
from .tables.items.item_position import ItemPosition
from .tables.order.order import Order
from .tables.order.order_scalar_counter import OrderScalarCounter
from .tables.order.order_delivery_window import OrderDeliveryWindow
from .tables.order.order_audit_log import OrderAuditLog
from .tables.order.order_event import OrderEvent
from .tables.order.order_event_action import OrderEventAction
from .tables.app_event_outbox import AppEventOutbox
from .tables.costumer.costumer import Costumer
from .tables.costumer.costumer_address import CostumerAddress
from .tables.costumer.costumer_phone import CostumerPhone
from .tables.costumer.costumer_operating_hours import CostumerOperatingHours
from .tables.route_operations.route_plan.route_plan import RoutePlan
DeliveryPlan = RoutePlan
from .tables.route_operations.route_plan.route_plan_event import RoutePlanEvent
from .tables.route_operations.route_plan.route_plan_event_action import RoutePlanEventAction
from .tables.route_operations.route_plan.route_group import RouteGroup
from .tables.international_shipping_plan.international_shipping_plan import (
    InternationalShippingPlan,
)
from .tables.store_pickup_plan.store_pickup_plan import StorePickupPlan
from .tables.route_operations.route_plan.route_solution import (
    RouteSolution,
)
from .tables.route_operations.route_plan.route_stop import (
    RouteSolutionStop,
)
from .tables.route_operations.route_plan.route_plan_state import RoutePlanState
from .tables.order.order_state import OrderState
from .tables.order.order_state_history import OrderStateHistory
from .tables.order.order_case import OrderCase, CaseChat
from .tables.notifications.notification_read import NotificationRead
from .tables.integrations.email_integration import EmailSMTP
from .tables.integrations.twilio_integration import TwilioMod
from .tables.content_templates.message_template import MessageTemplate
from .tables.content_templates.label_template import LabelTemplate
from .tables.integrations.shopify_integration import OAuthState
from .tables.integrations.shopify_integration import ShopifyIntegration
from .tables.integrations.shopify_integration import ShopifyWebhookEvents
from .tables.integrations.order_schedule_target import OrderScheduleTarget
from .tables.analytics.route_metrics_snapshot import RouteMetricsSnapshot as AnalyticsRouteMetricsSnapshot
from .tables.analytics.analytics_daily_fact import AnalyticsDailyFact
from .tables.zones.zone_version import ZoneVersion
from .tables.zones.zone import Zone
from .tables.zones.zone_template import ZoneTemplate
from .tables.zones.order_zone_assignment import OrderZoneAssignment
from .tables.notifications.push_subscription import PushSubscription
