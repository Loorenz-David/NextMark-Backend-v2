from types import SimpleNamespace

from Delivery_app_BK.services.infra.messaging.label_resolvers import (
    MessageRenderContext,
    resolve_label,
)


def test_resolve_client_form_link_uses_extra_context():
    context = MessageRenderContext(
        order=SimpleNamespace(),
        extra_context={"client_form_link": "https://forms.nextmark.app/form/token123"},
    )

    assert resolve_label("client_form_link", context, channel="email") == "https://forms.nextmark.app/form/token123"


def test_resolve_client_form_link_returns_empty_string_when_missing():
    context = MessageRenderContext(order=SimpleNamespace())

    assert resolve_label("client_form_link", context, channel="sms") == ""