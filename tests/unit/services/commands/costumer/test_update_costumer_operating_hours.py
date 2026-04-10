from importlib import import_module
from types import SimpleNamespace

module = import_module("Delivery_app_BK.services.commands.costumer.update_costumer")


class _FakeSession:
    def __init__(self) -> None:
        self.deleted: list[object] = []
        self.flush_calls = 0

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    def flush(self) -> None:
        self.flush_calls += 1


def _build_instance() -> SimpleNamespace:
    return SimpleNamespace(
        id=3,
        operating_hours=[
            SimpleNamespace(
                weekday=0,
                open_time="08:00",
                close_time="16:00",
                is_closed=False,
                client_id="existing_0",
            ),
            SimpleNamespace(
                weekday=1,
                open_time="08:00",
                close_time="16:00",
                is_closed=False,
                client_id="existing_1",
            ),
            SimpleNamespace(
                weekday=2,
                open_time="08:00",
                close_time="16:00",
                is_closed=False,
                client_id="existing_2",
            ),
        ],
    )


def test_replace_operating_hours_flushes_deletes_before_reinsert(monkeypatch):
    fake_session = _FakeSession()
    instance = _build_instance()
    previous_rows = list(instance.operating_hours)
    payload = [
        {
            "client_id": "new_0",
            "weekday": 0,
            "open_time": "09:00",
            "close_time": "17:00",
            "is_closed": False,
        },
        {
            "client_id": "new_1",
            "weekday": 1,
            "open_time": "10:00",
            "close_time": "18:00",
            "is_closed": False,
        },
        {
            "client_id": "new_5",
            "weekday": 5,
            "open_time": "09:00",
            "close_time": "17:00",
            "is_closed": False,
        },
    ]

    monkeypatch.setattr(module.db, "session", fake_session, raising=False)

    module._apply_operating_hours_mutations(
        instance,
        {"replace_operating_hours": True, "operating_hours": payload},
        team_id=3,
    )

    assert fake_session.deleted == previous_rows
    assert fake_session.flush_calls == 1
    assert [row.weekday for row in instance.operating_hours] == [0, 1, 5]
    assert [row.client_id for row in instance.operating_hours] == ["new_0", "new_1", "new_5"]
    assert [row.open_time for row in instance.operating_hours] == ["09:00", "10:00", "09:00"]


def test_non_replace_updates_existing_and_inserts_missing_without_duplicates(monkeypatch):
    fake_session = _FakeSession()
    instance = _build_instance()
    existing_row = instance.operating_hours[1]

    monkeypatch.setattr(module.db, "session", fake_session, raising=False)
    monkeypatch.setattr(module, "generate_client_id", lambda _prefix: "generated_operating_hour")

    module._apply_operating_hours_mutations(
        instance,
        {
            "operating_hours": [
                {
                    "weekday": 1,
                    "open_time": "11:00",
                    "close_time": "19:00",
                    "is_closed": False,
                },
                {
                    "weekday": 5,
                    "open_time": "09:00",
                    "close_time": "17:00",
                    "is_closed": True,
                },
            ]
        },
        team_id=3,
    )

    assert fake_session.deleted == []
    assert fake_session.flush_calls == 0
    assert existing_row.open_time == "11:00"
    assert existing_row.close_time == "19:00"
    assert existing_row.is_closed is False

    weekdays = [row.weekday for row in instance.operating_hours]
    assert weekdays.count(1) == 1
    assert weekdays.count(5) == 1

    inserted = next(row for row in instance.operating_hours if row.weekday == 5)
    assert inserted.client_id == "generated_operating_hour"
    assert inserted.is_closed is True


def test_replace_with_frontend_row_shape_including_client_ids_is_supported(monkeypatch):
    fake_session = _FakeSession()
    instance = _build_instance()
    payload = [
        {
            "client_id": "costumer_operating_hours_a",
            "weekday": 0,
            "open_time": "09:00",
            "close_time": "17:00",
            "is_closed": False,
        },
        {
            "client_id": "costumer_operating_hours_b",
            "weekday": 6,
            "open_time": "09:00",
            "close_time": "17:00",
            "is_closed": True,
        },
    ]

    monkeypatch.setattr(module.db, "session", fake_session, raising=False)

    module._apply_operating_hours_mutations(
        instance,
        {"replace_operating_hours": True, "operating_hours": payload},
        team_id=3,
    )

    assert fake_session.flush_calls == 1
    assert [row.weekday for row in instance.operating_hours] == [0, 6]
    assert [row.client_id for row in instance.operating_hours] == [
        "costumer_operating_hours_a",
        "costumer_operating_hours_b",
    ]
    assert instance.operating_hours[1].is_closed is True
