from enum import Enum


class OrderState(str, Enum):
    DRAFT = "Draft"
    CONFIRMED = "Confirmed"
    PREPARING = "Preparing"
    READY = "Ready"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAIL = "Fail"
    CANCELLED = "Cancelled"


class OrderStateId:
    DRAFT = 1
    CONFIRMED = 2
    PREPARING = 3
    READY = 4
    PROCESSING = 5
    COMPLETED = 6
    FAIL = 7
    CANCELLED = 8