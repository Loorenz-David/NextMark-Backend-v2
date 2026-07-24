from importlib import import_module
from types import SimpleNamespace

import pytest

# services.commands.order and services.infra.tasks.order import each other, so
# the task modules cannot be the entry point of the import graph. Importing the
# commands package first resolves the cycle and lets this module be collected
# on its own rather than only as part of a wider run.
import_module("Delivery_app_BK.services.commands.order")

email_module = import_module("Delivery_app_BK.services.infra.tasks.order.send_email")
sms_module = import_module("Delivery_app_BK.services.infra.tasks.order.send_sms")


MODULES = pytest.mark.parametrize("module", [email_module, sms_module])


def _action(payload):
    return SimpleNamespace(
        payload=payload,
        event=SimpleNamespace(event_name="order_manual_message"),
    )


@MODULES
def test_manual_action_resolves_the_template_event_from_its_payload(module):
    action = _action({"template_event": " order_ready ", "manual": True})

    assert module._resolve_template_event_name(action) == "order_ready"


@MODULES
def test_automatic_action_falls_back_to_its_own_event(module):
    action = _action(None)

    assert module._resolve_template_event_name(action) == "order_manual_message"


@MODULES
@pytest.mark.parametrize(
    "payload",
    [{}, {"shopify_order_id": 5}, {"template_event": ""}, {"template_event": 7}],
)
def test_payloads_without_a_usable_template_event_fall_back(module, payload):
    action = _action(payload)

    assert module._resolve_template_event_name(action) == "order_manual_message"


@MODULES
def test_actions_without_a_payload_attribute_fall_back(module):
    action = SimpleNamespace(event=SimpleNamespace(event_name="order_created"))

    assert module._resolve_template_event_name(action) == "order_created"
