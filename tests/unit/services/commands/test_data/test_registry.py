import pytest

from Delivery_app_BK.services.commands.test_data.registry import (
    RefResolutionError,
    Registry,
)


def test_register_and_resolve():
    registry = Registry()

    registry.register("f1", 101)

    assert registry.resolve("f1") == 101


def test_resolve_unregistered_raises():
    registry = Registry()

    with pytest.raises(RefResolutionError):
        registry.resolve("missing")


def test_duplicate_sid_overwrites():
    registry = Registry()

    registry.register("f1", 101)
    registry.register("f1", 202)

    assert registry.resolve("f1") == 202


def test_reverse_lookup():
    registry = Registry()

    registry.register("f1", 101, "facility")

    assert registry.reverse_lookup("facility", 101) == "f1"


def test_reverse_lookup_unknown_raises():
    registry = Registry()

    with pytest.raises(RefResolutionError):
        registry.reverse_lookup("facility", 999)


def test_is_registered():
    registry = Registry()

    assert registry.is_registered("f1") is False

    registry.register("f1", 101)

    assert registry.is_registered("f1") is True
