from Delivery_app_BK.services.domain.item.item_states import ItemState, ItemStateId


ITEM_STATE_SEEDS = [
    {
        "id": ItemStateId.OPEN,
        "name": ItemState.OPEN.value,
        "color": "#2563EB",
        "default": True,
        "description": "Entry point for items.",
        "index": None,
        "is_system": True,
        "entry_point": ItemState.OPEN.value,
    },
    {
        "id": ItemStateId.COMPLETED,
        "name": ItemState.COMPLETED.value,
        "color": "#16A34A",
        "default": True,
        "description": "Item completed successfully.",
        "index": None,
        "is_system": True,
        "entry_point": ItemState.COMPLETED.value,
    },
    {
        "id": ItemStateId.FAIL,
        "name": ItemState.FAIL.value,
        "color": "#DC2626",
        "default": True,
        "description": "Item failed or cancelled.",
        "index": None,
        "is_system": True,
        "entry_point": ItemState.FAIL.value,
    },
]
