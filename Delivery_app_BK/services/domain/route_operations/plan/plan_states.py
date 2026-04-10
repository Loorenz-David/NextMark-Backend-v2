from enum import Enum


class PlanState(str, Enum):
    OPEN = "Open"
    READY = "Ready"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAIL = "Fail"


class PlanStateId:
    OPEN = 1
    READY = 2
    PROCESSING = 3
    COMPLETED = 4
    FAIL = 5


