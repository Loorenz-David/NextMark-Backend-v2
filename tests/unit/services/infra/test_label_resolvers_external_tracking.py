from types import SimpleNamespace

import pytest

from Delivery_app_BK.services.infra.messaging.label_resolvers import MessageRenderContext, resolve_label


def _context(**order_fields) -> MessageRenderContext:
    return MessageRenderContext(order=SimpleNamespace(**order_fields))


@pytest.mark.parametrize("channel", ["sms", "email"])
def test_external_tracking_labels_read_the_courier_fields(channel):
    context = _context(
        tracking_number="NM-0001",
        tracking_link="https://track.nextmark.app/NM-0001",
        external_tracking_number="  1Z999AA10123456784 ",
        external_tracking_link="https://ups.com/track?loc=en_US&tracknum=1Z999AA10123456784",
    )

    assert resolve_label("external_tracking_number", context, channel) == "1Z999AA10123456784"
    assert (
        resolve_label("external_tracking_link", context, channel)
        == "https://ups.com/track?loc=en_US&tracknum=1Z999AA10123456784"
    )
    # The system-generated pair is untouched and distinct.
    assert resolve_label("tracking_number", context, channel) == "NM-0001"


def test_external_tracking_labels_render_empty_when_the_order_has_none():
    context = _context(external_tracking_number=None, external_tracking_link=None)

    assert resolve_label("external_tracking_number", context, "sms") == ""
    assert resolve_label("external_tracking_link", context, "email") == ""
