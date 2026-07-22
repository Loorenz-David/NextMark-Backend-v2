import hashlib
import importlib
from types import SimpleNamespace

import pytest

module = importlib.import_module(
    "Delivery_app_BK.services.commands.order.tracking.generate_tracking_identifiers"
)


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        (
            SimpleNamespace(
                external_source="shopify",
                reference_number="#5001",
                order_scalar_id=1000,
                id=42,
            ),
            "5001",
        ),
        (
            SimpleNamespace(
                external_source="shopify",
                reference_number="  5001  ",
                order_scalar_id=1000,
                id=42,
            ),
            "5001",
        ),
        (
            SimpleNamespace(
                external_source="shopify",
                reference_number=" # ",
                order_scalar_id=1000,
                id=42,
            ),
            "TRK-1000",
        ),
        (
            SimpleNamespace(
                external_source="shopify",
                reference_number=None,
                order_scalar_id=None,
                id=42,
            ),
            "TRK-42",
        ),
        (
            SimpleNamespace(
                external_source="manual",
                reference_number="#5001",
                order_scalar_id=1000,
                id=42,
            ),
            "TRK-1000",
        ),
        (
            SimpleNamespace(
                external_source=None,
                reference_number=None,
                order_scalar_id=None,
                id=42,
            ),
            "TRK-42",
        ),
    ],
)
def test_resolve_tracking_number_uses_expected_precedence(order, expected):
    assert module.resolve_tracking_number(order) == expected


def test_generate_tracking_identifiers_keeps_secure_fields_unchanged_in_shape(monkeypatch):
    order = SimpleNamespace(
        external_source="shopify",
        reference_number="#5001",
        order_scalar_id=1000,
        id=42,
    )
    raw_token = "raw-token"
    monkeypatch.setattr(module.secrets, "token_urlsafe", lambda _size: raw_token)

    result = module.generate_tracking_identifiers(order)

    assert result == {"raw_token": raw_token}
    assert order.tracking_number == "5001"
    assert order.tracking_token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
    assert order.tracking_link == f"https://tracking.nextmark.app/track/{raw_token}"
    assert order.tracking_token_created_at.tzinfo is not None
