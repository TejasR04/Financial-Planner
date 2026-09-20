from app.api.v1.routes.agent import _activity_selection_query


def test_follow_up_activity_query_carries_prior_user_topic() -> None:
    history = [
        {"role": "user", "content": "How much am I spending on Transportation?"},
        {"role": "assistant", "content": "You spent $24.50."},
    ]

    query = _activity_selection_query("Compare to other previous months", history)

    assert query.startswith("Compare to other previous months")
    assert "Transportation" in query


def test_standalone_activity_query_does_not_mix_in_prior_topic() -> None:
    history = [{"role": "user", "content": "Show my Starbucks transactions"}]

    assert _activity_selection_query("How much did I spend on Dining?", history) == (
        "How much did I spend on Dining?"
    )
