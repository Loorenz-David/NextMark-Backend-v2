import importlib


module = importlib.import_module(
    "migrations.versions.t9u5v1w7x3y0_recalculate_shopify_tracking_numbers"
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Bind:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))
        if sql.lstrip().upper().startswith("SELECT"):
            return _Result(self.rows)
        return _Result([])


def test_recalculate_shopify_tracking_numbers_updates_only_tracking_number():
    bind = _Bind(
        [
            (1, "shopify", "#5001", 1000),
            (2, "shopify", " # ", None),
        ]
    )

    updated = module._recalculate_shopify_tracking_numbers(bind)

    assert updated == 2
    update_calls = bind.calls[1:]
    assert [params for _sql, params in update_calls] == [
        {"tracking_number": "5001", "order_id": 1},
        {"tracking_number": "TRK-2", "order_id": 2},
    ]
    assert all("tracking_token_hash" not in sql for sql, _params in update_calls)
    assert all("tracking_link" not in sql for sql, _params in update_calls)
