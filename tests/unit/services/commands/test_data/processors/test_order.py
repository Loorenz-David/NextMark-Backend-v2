from Delivery_app_BK.services.commands.test_data.processors import order as module


def test_process_calls_service_and_returns_id(monkeypatch):
    calls = []

    def fake_create_order(ctx):
        calls.append(ctx.incoming_data)
        return {"created": [{"order": {"id": 77}}]}

    monkeypatch.setattr(module, "create_order", fake_create_order)

    result = module.process(
        {
            "reference_number": "test-001",
            "items": [{"article_number": "CHAIR-1", "item_type": "test-Chair"}],
        },
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert result == 77
    assert calls == [
        {
            "fields": [
                {
                    "reference_number": "test-001",
                    "items": [
                        {
                            "article_number": "CHAIR-1",
                            "item_type": "test-Chair",
                            "client_id": calls[0]["fields"][0]["items"][0]["client_id"],
                        }
                    ],
                }
            ]
        }
    ]
    assert calls[0]["fields"][0]["items"][0]["client_id"].startswith("item:")


def test_process_assigns_client_ids_to_inline_items_and_windows(monkeypatch):
    calls = []

    def fake_create_order(ctx):
        calls.append(ctx.incoming_data)
        return {"created": [{"order": {"id": 77}}]}

    monkeypatch.setattr(module, "create_order", fake_create_order)

    module.process(
        {
            "reference_number": "test-001",
            "items": [{"article_number": "CHAIR-1"}],
            "delivery_windows": [{"start_at": "a", "end_at": "b", "window_type": "TIME_RANGE"}],
        },
        {"team_id": 5, "user_id": 1},
        None,
    )

    fields = calls[0]["fields"][0]
    assert fields["items"][0]["client_id"].startswith("item:")
    assert fields["delivery_windows"][0]["client_id"].startswith("order_delivery_window:")
