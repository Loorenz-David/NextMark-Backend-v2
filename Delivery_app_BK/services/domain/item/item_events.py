
from enum import Enum

class itemEvent(str, Enum):
    CREATED = "item_created"
    EDITED = "item_edited"
    RESCHEDULED = "item_rescheduled"







class itemEventPrintDocuments(str,Enum):
    CREATED = itemEvent.CREATED.value
    EDITED = itemEvent.EDITED.value
    RESCHEDULED = itemEvent.RESCHEDULED.value