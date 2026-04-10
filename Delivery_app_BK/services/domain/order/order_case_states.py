from enum import Enum


class OrderCaseState(str, Enum):
    OPEN = "Open"
    RESOLVING = "Resolving"
    RESOLVED = "Resolved"
  
