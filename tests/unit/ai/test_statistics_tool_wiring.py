from Delivery_app_BK.ai.capabilities.statistics.registry import STATISTICS_TOOLS
from Delivery_app_BK.ai.prompts.statistics_execute_prompt import build_statistics_execute_prompt


def test_statistics_tools_include_extended_read_only_analytics():
    assert set(STATISTICS_TOOLS.keys()) == {
        "get_analytics_snapshot",
        "get_daily_summary",
        "get_route_metrics_tool",
    }


def test_statistics_prompt_advertises_extended_tooling():
    prompt = build_statistics_execute_prompt()
    assert "get_analytics_snapshot" in prompt
    assert "get_daily_summary" in prompt
    assert "get_route_metrics_tool" in prompt
