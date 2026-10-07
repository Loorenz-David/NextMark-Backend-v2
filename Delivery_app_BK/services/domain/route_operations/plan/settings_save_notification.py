from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PLAN_CHANGE_DATES = "dates"
PLAN_CHANGE_NAME = "name"
PLAN_CHANGE_ROUTE_SETTINGS = "route settings"


@dataclass(frozen=True)
class SettingsSaveNotification:
    kind: Literal["plan", "route"]
    # What the plan notification says changed, e.g. ["dates", "route settings"].
    plan_changes: tuple[str, ...] = ()


def resolve_settings_save_notification(
    *,
    dates_changed: bool,
    label_changed: bool,
    route_settings_changed: bool,
    driver_changed: bool,
) -> SettingsSaveNotification | None:
    """The one notification a plan-settings save sends.

    A change to the plan itself is reported once, at the plan level — the
    route re-timing that follows moved dates is part of that change, not a
    second update. A save that only touched the route is reported on the
    route. A driver assignment has its own notification, so it suppresses
    the route one.
    """
    plan_changes: list[str] = []
    if dates_changed:
        plan_changes.append(PLAN_CHANGE_DATES)
    if label_changed:
        plan_changes.append(PLAN_CHANGE_NAME)

    if plan_changes:
        if route_settings_changed:
            plan_changes.append(PLAN_CHANGE_ROUTE_SETTINGS)
        return SettingsSaveNotification(kind="plan", plan_changes=tuple(plan_changes))

    if route_settings_changed and not driver_changed:
        return SettingsSaveNotification(kind="route")

    return None
