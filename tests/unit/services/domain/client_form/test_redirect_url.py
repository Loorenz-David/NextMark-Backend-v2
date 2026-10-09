import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.client_form.redirect_url import (
    MAX_REDIRECT_URL_LENGTH,
    normalize_redirect_label,
    normalize_redirect_url,
    redirect_url_host,
)


class TestNormalizeRedirectUrl:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("https://acme.se", "https://acme.se"),
            ("  https://acme.se/thank-you?ref=form#top  ", "https://acme.se/thank-you?ref=form#top"),
            ("HTTPS://ACME.SE/Path", "https://acme.se/Path"),
            ("https://acme.se:443/x", "https://acme.se/x"),
            ("https://acme.se:8443/x", "https://acme.se:8443/x"),
            ("https://shop.acme.co.uk/", "https://shop.acme.co.uk/"),
            ("https://acme.se./x", "https://acme.se/x"),
            # Unicode hostnames are stored as punycode, so a look-alike domain
            # is shown to admins and customers in its real form.
            ("https://bücher.de/", "https://xn--bcher-kva.de/"),
        ],
    )
    def test_accepts_and_normalizes_public_https_urls(self, raw, expected):
        assert normalize_redirect_url(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "",
            "   ",
            123,
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox",
            "http://acme.se",
            "ftp://acme.se",
            "//acme.se",
            "acme.se",
            "https://",
            "https:///path",
            "https://user:pass@acme.se",
            "https://acme.se@evil.example",
            "https://acme.se\\@evil.example",
            "https://acme.se/\\evil",
            "https://acme .se",
            "https://acme.se/\npath",
            "https://acme.se/\tpath",
            "https://127.0.0.1/",
            "https://10.0.0.5/",
            "https://[::1]/",
            "https://localhost/",
            "https://intranet/",
            "https://printer.local/",
            "https://api.internal/",
            "https://acme.se:99999/",
        ],
    )
    def test_rejects_unsafe_or_malformed_urls(self, raw):
        with pytest.raises(ValidationFailed):
            normalize_redirect_url(raw)

    def test_rejects_overlong_urls(self):
        url = "https://acme.se/" + "a" * MAX_REDIRECT_URL_LENGTH
        with pytest.raises(ValidationFailed, match="longer than"):
            normalize_redirect_url(url)

    def test_is_idempotent(self):
        once = normalize_redirect_url("https://Bücher.de/x?y=1")
        assert normalize_redirect_url(once) == once


def test_redirect_url_host_returns_hostname_without_port():
    assert redirect_url_host("https://acme.se:8443/x") == "acme.se"


class TestNormalizeRedirectLabel:
    def test_strips(self):
        assert normalize_redirect_label("  Our site ") == "Our site"

    @pytest.mark.parametrize("raw", [None, "", "  ", "x" * 81])
    def test_rejects_missing_or_long(self, raw):
        with pytest.raises(ValidationFailed):
            normalize_redirect_label(raw)
