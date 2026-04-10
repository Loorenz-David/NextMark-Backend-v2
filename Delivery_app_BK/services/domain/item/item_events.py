
from enum import Enum

class itemEvent(str, Enum):
    CREATED = "item_created"
    EDITED = "item_edited"







class itemEventPrintDocuments(str,Enum):
    CREATED = itemEvent.CREATED.value
    EDITED = itemEvent.EDITED.value
