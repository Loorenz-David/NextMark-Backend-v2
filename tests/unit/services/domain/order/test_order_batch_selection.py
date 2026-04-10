import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.order.order_batch_selection import (
    MAX_RESOLVED_COUNT,
    SAMPLE_IDS_LIMIT,
    _ensure_max_resolved_count,
    _is_statement_timeout_error,
)


class _FakeTimeoutError(Exception):
    def __init__(self, pgcode=None, message: str = ""):
        super().__init__(message)
        self.pgcode = pgcode


class _FakeDBAPIError:
    def __init__(self, orig=None, message: str = ""):
        self.orig = orig
        self._message = message

    def __str__(self):
        return self._message


def test_max_resolved_count_guard_allows_limit():
    _ensure_max_resolved_count(MAX_RESOLVED_COUNT)


def test_max_resolved_count_guard_rejects_over_limit():
    with pytest.raises(ValidationFailed):
        _ensure_max_resolved_count(MAX_RESOLVED_COUNT + 1)


def test_statement_timeout_detection_by_pg_code():
    exc = _FakeDBAPIError(orig=_FakeTimeoutError(pgcode="57014"))
    assert _is_statement_timeout_error(exc) is True


def test_statement_timeout_detection_by_message():
    exc = _FakeDBAPIError(message="canceling statement due to statement timeout")
    assert _is_statement_timeout_error(exc) is True


def test_sample_limit_constant_is_50():
    assert SAMPLE_IDS_LIMIT == 50
