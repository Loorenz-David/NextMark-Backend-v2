from Delivery_app_BK.services.infra.messaging import template_resolver


class _FakeQuery:
    def __init__(self, result, clauses):
        self._result = result
        self.clauses = clauses

    def filter(self, *clauses):
        self.clauses.extend(str(clause) for clause in clauses)
        return self

    def first(self):
        return self._result


def _install_fake_query(monkeypatch, result):
    clauses: list[str] = []
    monkeypatch.setattr(
        template_resolver.db.session,
        "query",
        lambda _model: _FakeQuery(result, clauses),
    )
    return clauses


def test_resolver_filters_on_plan_type(monkeypatch):
    sentinel = object()
    clauses = _install_fake_query(monkeypatch, sentinel)

    found = template_resolver.resolve_message_template(
        team_id=7,
        channel="sms",
        event_name="order_ready",
        plan_type="store_pickup",
    )

    assert found is sentinel
    assert any("message_template.plan_type" in clause for clause in clauses)
    assert any("message_template.channel" in clause for clause in clauses)
    assert any("message_template.event" in clause for clause in clauses)
    assert not any("message_template.enable" in clause for clause in clauses)


def test_resolver_adds_enable_filter_only_when_asked(monkeypatch):
    clauses = _install_fake_query(monkeypatch, None)

    template_resolver.resolve_message_template(
        team_id=7,
        channel="email",
        event_name="order_ready",
        plan_type="local_delivery",
        enabled_only=True,
    )

    assert any("message_template.enable IS true" in clause for clause in clauses)


def test_resolver_short_circuits_without_a_team(monkeypatch):
    def _boom(_model):
        raise AssertionError("query must not run without a team")

    monkeypatch.setattr(template_resolver.db.session, "query", _boom)

    assert (
        template_resolver.resolve_message_template(
            team_id=None,
            channel="sms",
            event_name="order_ready",
            plan_type="store_pickup",
        )
        is None
    )
