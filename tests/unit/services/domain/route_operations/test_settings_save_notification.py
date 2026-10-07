from Delivery_app_BK.services.domain.route_operations.plan.settings_save_notification import (
    SettingsSaveNotification,
    resolve_settings_save_notification,
)


def _resolve(**overrides):
    flags = {
        "dates_changed": False,
        "label_changed": False,
        "route_settings_changed": False,
        "driver_changed": False,
        **overrides,
    }
    return resolve_settings_save_notification(**flags)


def test_moving_plan_dates_is_one_plan_notification_even_though_the_route_retimes():
    assert _resolve(dates_changed=True) == SettingsSaveNotification(
        kind="plan", plan_changes=("dates",)
    )


def test_plan_notification_lists_route_settings_saved_alongside():
    assert _resolve(
        dates_changed=True, label_changed=True, route_settings_changed=True
    ) == SettingsSaveNotification(
        kind="plan", plan_changes=("dates", "name", "route settings")
    )


def test_route_only_save_is_reported_on_the_route():
    assert _resolve(route_settings_changed=True) == SettingsSaveNotification(kind="route")


def test_driver_assignment_has_its_own_notification():
    assert _resolve(route_settings_changed=True, driver_changed=True) is None


def test_save_without_changes_sends_nothing():
    assert _resolve() is None
