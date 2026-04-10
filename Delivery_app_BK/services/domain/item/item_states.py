from enum import Enum

class ItemState(str, Enum):
    OPEN = "Open"
    COMPLETED = "Completed"
    FAIL = "Failed"

class ItemStateId:
    OPEN = 1
    COMPLETED = 2
    FAIL = 3
