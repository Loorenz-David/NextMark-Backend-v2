from Delivery_app_BK.ai.prompts.statistics_execute_prompt import build_statistics_execute_prompt


def test_statistics_execute_prompt_includes_team_context_fields():
    prompt = build_statistics_execute_prompt(
        time_zone="Europe/Stockholm",
        current_time="2026-03-22T14:30:00+01:00",
        default_country_code="SE",
    )

    assert "Current team time: 2026-03-22T14:30:00+01:00" in prompt
    assert "Team timezone: Europe/Stockholm" in prompt
    assert "Team country code: SE" in prompt


def test_statistics_execute_prompt_defaults_without_team_context():
    prompt = build_statistics_execute_prompt()

    assert "You are a senior logistics data analyst." in prompt
    assert "TIMEFRAME RULES:" in prompt
    assert "get_daily_summary" in prompt
    assert "get_route_metrics_tool" in prompt
