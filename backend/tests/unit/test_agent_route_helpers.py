from app.api.v1.routes.agent import _activity_selection_query, _conversation_title


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


def test_conversation_title_is_compact_and_single_line() -> None:
    title = _conversation_title("  Compare my dining\nspending " + "last year " * 20)

    assert "\n" not in title
    assert len(title) <= 80
    assert title.endswith("...")
