import importlib
from types import SimpleNamespace

module = importlib.import_module(
    "Delivery_app_BK.services.queries.client_form_config.resolve_public_redirect"
)


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self._result


def test_returns_none_without_an_active_redirect(monkeypatch):
    monkeypatch.setattr(module.db.session, "query", lambda model: _FakeQuery(None))
    assert module.resolve_public_redirect(7) is None


def test_returns_normalized_url_and_host(monkeypatch):
    row = SimpleNamespace(id=1, url="https://Acme.se/thanks")
    monkeypatch.setattr(module.db.session, "query", lambda model: _FakeQuery(row))
    assert module.resolve_public_redirect(7) == {
        "url": "https://acme.se/thanks",
        "host": "acme.se",
    }


def test_drops_a_stored_url_that_no_longer_validates(monkeypatch):
    row = SimpleNamespace(id=1, url="javascript:alert(1)")
    monkeypatch.setattr(module.db.session, "query", lambda model: _FakeQuery(row))
    assert module.resolve_public_redirect(7) is None
