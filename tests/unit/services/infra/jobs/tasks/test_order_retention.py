from Delivery_app_BK.services.infra.jobs.tasks import order_retention


def _patch(monkeypatch, *, order_ids_by_team, delete_order):
    rollbacks = {"count": 0}

    monkeypatch.setattr(
        "Delivery_app_BK.services.queries.order.find_discardable_unplanned_orders."
        "find_discardable_unplanned_orders",
        lambda *, now, limit: order_ids_by_team,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.order.delete_order.delete_order",
        delete_order,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.models.db.session.rollback",
        lambda: rollbacks.__setitem__("count", rollbacks["count"] + 1),
    )
    return rollbacks


def test_purge_deletes_each_teams_orders_in_its_own_team_scope(monkeypatch):
    calls = []

    def _delete_order(ctx):
        calls.append((ctx.team_id, ctx.incoming_data["target_ids"]))

    _patch(monkeypatch, order_ids_by_team={3: [10, 11], 4: [20]}, delete_order=_delete_order)

    purged = order_retention.purge_unplanned_orders_job()

    assert purged == 3
    assert calls == [(3, [10, 11]), (4, [20])]


def test_purge_isolates_a_failing_team(monkeypatch):
    calls = []

    def _delete_order(ctx):
        calls.append(ctx.team_id)
        if ctx.team_id == 3:
            raise RuntimeError("boom")

    rollbacks = _patch(
        monkeypatch,
        order_ids_by_team={3: [10], 4: [20, 21]},
        delete_order=_delete_order,
    )

    purged = order_retention.purge_unplanned_orders_job()

    assert calls == [3, 4]
    assert purged == 2
    assert rollbacks["count"] == 1


def test_purge_is_a_no_op_without_candidates(monkeypatch):
    def _delete_order(_ctx):
        raise AssertionError("delete_order must not be called")

    _patch(monkeypatch, order_ids_by_team={}, delete_order=_delete_order)

    assert order_retention.purge_unplanned_orders_job() == 0
