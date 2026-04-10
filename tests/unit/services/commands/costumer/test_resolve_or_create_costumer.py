from types import SimpleNamespace
import importlib

module = importlib.import_module(
    "Delivery_app_BK.services.commands.costumer.resolve_or_create_costumer"
)


def test_resolve_batch_uses_explicit_costumer_id(monkeypatch):
    explicit = SimpleNamespace(id=11)

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {11: explicit})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {})
    monkeypatch.setattr(module, "_create_costumer_from_snapshot", lambda **_kwargs: None)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [module.CostumerResolutionInput(costumer_id=11)],
    )

    assert resolved == [explicit]


def test_resolve_batch_uses_explicit_costumer_client_id(monkeypatch):
    by_client = SimpleNamespace(id=12)

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {"costumer_12": by_client})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {})
    monkeypatch.setattr(module, "_create_costumer_from_snapshot", lambda **_kwargs: None)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [module.CostumerResolutionInput(costumer_client_id="costumer_12")],
    )

    assert resolved == [by_client]


def test_resolve_batch_prefers_email_match(monkeypatch):
    by_email = SimpleNamespace(id=20)
    by_phone = SimpleNamespace(id=21)

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {"test@mail.com": by_email})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {"+1555": by_phone})
    monkeypatch.setattr(module, "_create_costumer_from_snapshot", lambda **_kwargs: None)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [
            module.CostumerResolutionInput(
                email="TEST@mail.com",
                primary_phone={"prefix": "+1", "number": "555"},
            )
        ],
    )

    assert resolved == [by_email]


def test_resolve_batch_uses_phone_when_no_email_match(monkeypatch):
    by_phone = SimpleNamespace(id=30)

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {"+46700": by_phone})
    monkeypatch.setattr(module, "_create_costumer_from_snapshot", lambda **_kwargs: None)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [
            module.CostumerResolutionInput(
                email=None,
                primary_phone={"prefix": "+46", "number": "700"},
            )
        ],
    )

    assert resolved == [by_phone]


def test_resolve_batch_creates_when_no_match_exists(monkeypatch):
    created = SimpleNamespace(id=40)
    create_calls = {"count": 0}

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {})

    def _create(**_kwargs):
        create_calls["count"] += 1
        return created

    monkeypatch.setattr(module, "_create_costumer_from_snapshot", _create)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [module.CostumerResolutionInput(first_name="No", last_name="Match")],
    )

    assert create_calls["count"] == 1
    assert resolved == [created]


def test_resolve_batch_reuses_created_costumer_for_same_email_in_batch(monkeypatch):
    created = SimpleNamespace(id=50)
    create_calls = {"count": 0}

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {})

    def _create(**_kwargs):
        create_calls["count"] += 1
        return created

    monkeypatch.setattr(module, "_create_costumer_from_snapshot", _create)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [
            module.CostumerResolutionInput(email="same@mail.com"),
            module.CostumerResolutionInput(email="SAME@mail.com"),
        ],
    )

    assert create_calls["count"] == 1
    assert resolved == [created, created]


def test_resolve_batch_handles_mixed_explicit_and_fallback(monkeypatch):
    explicit = SimpleNamespace(id=61)
    by_email = SimpleNamespace(id=62)

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {61: explicit})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {"mixed@mail.com": by_email})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {})
    monkeypatch.setattr(module, "_create_costumer_from_snapshot", lambda **_kwargs: None)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [
            module.CostumerResolutionInput(costumer_id=61),
            module.CostumerResolutionInput(email="mixed@mail.com"),
        ],
    )

    assert resolved == [explicit, by_email]


def test_resolve_batch_client_id_hint_reused_when_created(monkeypatch):
    created = SimpleNamespace(id=80)
    create_calls = {"count": 0}

    monkeypatch.setattr(module, "require_team_id", lambda _ctx: 1)
    monkeypatch.setattr(module, "_load_costumers_by_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_client_ids", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_email", lambda *_args: {})
    monkeypatch.setattr(module, "_load_costumers_by_phone", lambda *_args: {})

    def _create(**_kwargs):
        create_calls["count"] += 1
        return created

    monkeypatch.setattr(module, "_create_costumer_from_snapshot", _create)

    resolved = module.resolve_or_create_costumers(
        SimpleNamespace(),
        [
            module.CostumerResolutionInput(costumer_client_id="costumer_x"),
            module.CostumerResolutionInput(costumer_client_id="costumer_x"),
        ],
    )

    assert create_calls["count"] == 1
    assert resolved == [created, created]
