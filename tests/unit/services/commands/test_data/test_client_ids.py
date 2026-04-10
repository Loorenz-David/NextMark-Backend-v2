from Delivery_app_BK.services.commands.test_data import client_ids as module


def test_apply_test_data_client_id_adds_default_namespace():
    with module.test_data_client_id_namespace():
        result = module.apply_test_data_client_id("facility", {"name": "Depot"}, sid="f1")

    assert result["client_id"].startswith("td:facility:f1:")


def test_apply_test_data_client_id_ignores_entities_without_client_id_support():
    with module.test_data_client_id_namespace():
        result = module.apply_test_data_client_id("zone", {"name": "North"}, sid="z1")

    assert result == {"name": "North"}


def test_apply_test_data_client_id_to_order_children_tags_items_and_windows():
    with module.test_data_client_id_namespace():
        result = module.apply_test_data_client_id_to_order_children(
            {
                "items": [{"article_number": "A-1"}],
                "delivery_windows": [{"start_at": "a", "end_at": "b", "window_type": "TIME_RANGE"}],
            }
        )

    assert result["items"][0]["client_id"].startswith("td:item:item_0:")
    assert result["delivery_windows"][0]["client_id"].startswith(
        "td:order_delivery_window:window_0:"
    )


def test_resolve_test_data_client_id_prefix_reads_meta_override():
    prefix = module.resolve_test_data_client_id_prefix(
        {"_meta": {"client_id_prefix": "marker:"}}
    )

    assert prefix == "marker:"
