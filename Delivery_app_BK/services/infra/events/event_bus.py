from collections import defaultdict
from typing import Callable, DefaultDict, Iterable


EventHandler = Callable[[object], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, list[EventHandler]] = defaultdict(list)

    def register(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def get_handlers(self, event_name: str) -> Iterable[EventHandler]:
        return tuple(self._handlers.get(event_name, ()))

    def publish(self, order_event: object) -> None:
        event_name = getattr(order_event, "event_name", None)
        if not isinstance(event_name, str):
            return

        for handler in self.get_handlers(event_name):
            handler(order_event)
