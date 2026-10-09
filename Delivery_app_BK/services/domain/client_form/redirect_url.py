"""Validation for the page a customer is sent to after submitting the form.

The URL is typed by an admin and followed automatically by a customer's
browser, so it is held to a stricter standard than a link a person chooses to
tap: https only, a real public hostname, and nothing a browser could read
differently from how it looks on screen.
"""

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from Delivery_app_BK.errors import ValidationFailed

MAX_REDIRECT_URL_LENGTH = 2048
MAX_REDIRECT_LABEL_LENGTH = 80

# Names that only resolve inside a network, never to the team's public site.
_PRIVATE_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home.arpa")


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def normalize_redirect_url(raw: object) -> str:
    """Return the canonical form of an admin-entered redirect URL.

    Raises ValidationFailed when the value is not a public https URL.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationFailed("Redirect URL is required.")

    value = raw.strip()

    if len(value) > MAX_REDIRECT_URL_LENGTH:
        raise ValidationFailed(
            f"Redirect URL cannot be longer than {MAX_REDIRECT_URL_LENGTH} characters."
        )

    # Browsers treat a backslash as a slash, so `https://a.se\@b.se` would
    # open b.se while reading as a.se. Whitespace and control characters are
    # silently stripped by browsers in the same way.
    if "\\" in value or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise ValidationFailed("Redirect URL cannot contain spaces or special characters.")

    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValidationFailed("Redirect URL is not a valid address.")

    if parts.scheme.lower() != "https":
        raise ValidationFailed("Redirect URL must start with https://.")

    if not parts.netloc:
        raise ValidationFailed("Redirect URL must include a website address.")

    # `https://trusted.se@evil.se` opens evil.se.
    if "@" in parts.netloc:
        raise ValidationFailed("Redirect URL cannot contain a username or password.")

    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise ValidationFailed("Redirect URL must include a website address.")

    if _is_ip_literal(host):
        raise ValidationFailed("Redirect URL must use a domain name, not an IP address.")

    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValidationFailed("Redirect URL has an invalid domain name.")

    if (
        "." not in ascii_host
        or ascii_host == "localhost"
        or ascii_host.endswith(_PRIVATE_SUFFIXES)
    ):
        raise ValidationFailed("Redirect URL must point to a public website.")

    netloc = ascii_host if port is None or port == 443 else f"{ascii_host}:{port}"
    normalized = urlunsplit(("https", netloc, parts.path, parts.query, parts.fragment))

    if len(normalized) > MAX_REDIRECT_URL_LENGTH:
        raise ValidationFailed(
            f"Redirect URL cannot be longer than {MAX_REDIRECT_URL_LENGTH} characters."
        )

    return normalized


def redirect_url_host(url: str) -> str:
    """The hostname shown to the customer, taken from an already-normalized URL."""
    return urlsplit(url).hostname or ""


def normalize_redirect_label(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationFailed("Redirect name is required.")
    value = raw.strip()
    if len(value) > MAX_REDIRECT_LABEL_LENGTH:
        raise ValidationFailed(
            f"Redirect name cannot be longer than {MAX_REDIRECT_LABEL_LENGTH} characters."
        )
    return value
