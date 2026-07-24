from enum import Enum


class MediaPlacement(str, Enum):
    CAROUSEL = "carousel"
    SIDEBAR_LEFT = "sidebar_left"
    SIDEBAR_RIGHT = "sidebar_right"


ALLOWED_MEDIA_PLACEMENTS = {placement.value for placement in MediaPlacement}
