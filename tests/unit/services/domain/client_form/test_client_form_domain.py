import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.client_form.ordering import (
    next_position,
    normalize_positions,
)
from Delivery_app_BK.services.domain.client_form.terms import (
    next_version_number,
    requires_acceptance,
    validate_terms_content,
)


class TestNormalizePositions:
    def test_produces_gapless_sequence_from_zero(self):
        assert normalize_positions([9, 4, 7]) == [
            {"target_id": 9, "position": 0},
            {"target_id": 4, "position": 1},
            {"target_id": 7, "position": 2},
        ]

    def test_rejects_duplicates(self):
        with pytest.raises(ValidationFailed, match="Duplicate id"):
            normalize_positions([3, 3])

    def test_rejects_empty(self):
        with pytest.raises(ValidationFailed, match="at least one id"):
            normalize_positions([])

    def test_rejects_non_list(self):
        with pytest.raises(ValidationFailed, match="must be a list"):
            normalize_positions("1,2,3")


class TestNextPosition:
    def test_first_item_starts_at_zero(self):
        assert next_position([]) == 0

    def test_appends_above_the_maximum(self):
        assert next_position([0, 1, 5]) == 6


class TestNextVersionNumber:
    def test_first_version_is_one(self):
        assert next_version_number(None) == 1

    def test_increments(self):
        assert next_version_number(4) == 5

    def test_rejects_non_positive(self):
        with pytest.raises(ValidationFailed, match="must be positive"):
            next_version_number(0)


class TestValidateTermsContent:
    def test_accepts_object_and_array(self):
        assert validate_terms_content({"blocks": [1]}) == {"blocks": [1]}
        assert validate_terms_content([{"text": "hi"}]) == [{"text": "hi"}]

    @pytest.mark.parametrize("value", [None, {}, [], "plain string", 42])
    def test_rejects_empty_or_non_document(self, value):
        with pytest.raises(ValidationFailed):
            validate_terms_content(value)


class TestRequiresAcceptance:
    @pytest.mark.parametrize(
        "terms_enabled,require,expected",
        [(True, True, True), (True, False, False), (False, True, False), (False, False, False)],
    )
    def test_requires_both_flags(self, terms_enabled, require, expected):
        settings = type(
            "S", (), {"terms_enabled": terms_enabled, "require_acceptance": require}
        )()
        assert requires_acceptance(settings) is expected

    def test_absent_settings_never_requires_acceptance(self):
        assert requires_acceptance(None) is False
