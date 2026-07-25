import importlib
from types import SimpleNamespace

import pytest

module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.costumer."
    "sync_order_costumer_to_shopify"
)

CUSTOMER_GID = "gid://shopify/Customer/9257827467417"


def _order(marketing, *, client_email="buyer@example.com", costumer_email=None):
    return SimpleNamespace(
        id=1,
        marketing_messages=marketing,
        client_email=client_email,
        costumer=SimpleNamespace(email=costumer_email),
    )


# --- pure builder: True / False / None / missing email -----------------------


def test_consent_variables_subscribed_and_single_opt_in_when_true():
    variables = module._build_email_marketing_consent_variables(_order(True), CUSTOMER_GID)

    consent = variables["input"]["emailMarketingConsent"]
    assert variables["input"]["customerId"] == CUSTOMER_GID
    assert consent["marketingState"] == "SUBSCRIBED"
    assert consent["marketingOptInLevel"] == "SINGLE_OPT_IN"
    assert consent["consentUpdatedAt"].endswith("+00:00")


def test_consent_variables_unsubscribed_without_opt_in_when_false():
    variables = module._build_email_marketing_consent_variables(_order(False), CUSTOMER_GID)

    consent = variables["input"]["emailMarketingConsent"]
    assert consent["marketingState"] == "UNSUBSCRIBED"
    # Opt-in level is only meaningful when subscribing.
    assert "marketingOptInLevel" not in consent


def test_consent_variables_none_when_marketing_value_missing():
    assert module._build_email_marketing_consent_variables(_order(None), CUSTOMER_GID) is None


def test_consent_variables_none_when_email_missing():
    order = _order(True, client_email=None, costumer_email=None)
    assert module._build_email_marketing_consent_variables(order, CUSTOMER_GID) is None


def test_consent_variables_falls_back_to_costumer_email():
    order = _order(True, client_email=None, costumer_email="stored@example.com")
    variables = module._build_email_marketing_consent_variables(order, CUSTOMER_GID)
    assert variables is not None


# --- sync helper: calls / skips / propagates errors --------------------------


def test_sync_consent_posts_mutation_when_applicable(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        module,
        "_post_shopify_graphql",
        lambda **kwargs: calls.append(kwargs) or {"customerEmailMarketingConsentUpdate": {}},
    )

    integration = SimpleNamespace(shop="demo.myshopify.com", access_token="secret")
    module._sync_email_marketing_consent(_order(True), integration, CUSTOMER_GID)

    assert len(calls) == 1
    assert calls[0]["query"] is module.CUSTOMER_EMAIL_MARKETING_CONSENT_UPDATE_MUTATION
    consent = calls[0]["variables"]["input"]["emailMarketingConsent"]
    assert calls[0]["variables"]["input"]["customerId"] == CUSTOMER_GID
    assert consent["marketingState"] == "SUBSCRIBED"


@pytest.mark.parametrize(
    "order",
    [
        _order(None),
        _order(True, client_email=None, costumer_email=None),
    ],
)
def test_sync_consent_skips_when_not_applicable(monkeypatch, order):
    calls: list[dict] = []
    monkeypatch.setattr(module, "_post_shopify_graphql", lambda **kwargs: calls.append(kwargs))

    integration = SimpleNamespace(shop="demo.myshopify.com", access_token="secret")
    module._sync_email_marketing_consent(order, integration, CUSTOMER_GID)

    assert calls == []


def test_sync_consent_propagates_shopify_error(monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("Shopify customerEmailMarketingConsentUpdate userErrors: [...]")

    monkeypatch.setattr(module, "_post_shopify_graphql", _raise)

    integration = SimpleNamespace(shop="demo.myshopify.com", access_token="secret")
    with pytest.raises(RuntimeError):
        module._sync_email_marketing_consent(_order(True), integration, CUSTOMER_GID)
