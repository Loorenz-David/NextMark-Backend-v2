from enum import Enum


class OrderEvent(str, Enum):
    CREATED = "order_created"
    CONFIRMED = "order_confirmed"
    PREPARING = "order_preparing"
    EDITED = "order_edited"
    READY = "order_ready"
    PROCESSING = "order_processing"
    COMPLETED = "order_completed"
    FAIL = "order_failed"
    CANCELLED = "order_cancelled"
    STATUS_CHANGED = "order_status_changed"
    DELIVERY_WINDOW_RESCHEDULED_BY_USER = "order_delivery_window_changed_by_user"
    DELIVERY_PLAN_CHANGED = "order_delivery_plan_changed"
    DELIVERY_RESCHEDULED = "order_rescheduled"
    CLIENT_FORM_LINK_SENT = "client_form_link_sent"


class OrderEventPrintDocuments(str,Enum):
    CREATED = OrderEvent.CREATED.value
    CONFIRMED = OrderEvent.CONFIRMED.value
    EDITED = OrderEvent.EDITED.value


"""
Delivery plan changed happes when a order changes of delivery plan type, 

Order_rescheduled happens when a delivery plan changes it's dates. or when an order changes
of plan and dates are not the same as the previous plan dates 

DELIVERY_WINDOW_RESCHEDULED_BY_USER happens when a user changes the window of an order manually,
this windows are bounderies not clear dates 


"""
