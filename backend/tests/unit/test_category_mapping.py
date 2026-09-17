from uuid import uuid4
import pytest
from app.domain.category_mapping import match_existing_category
from app.persistence.repositories.user_repository import DEFAULT_BUDGET_CATEGORIES


def test_detailed_food_category_selects_groceries_over_dining():
    groceries, dining = uuid4(), uuid4()
    assert match_existing_category("FOOD_AND_DRINK_GROCERIES", [(groceries, "Groceries"), (dining, "Dining")]) == groceries


def test_aliases_use_existing_category_and_exact_custom_names():
    category = uuid4()
    assert match_existing_category("FOOD_AND_DRINK", [(category, "Dining out")]) == category
    assert match_existing_category("PET_CARE", [(category, "Pet care")]) == category


def test_ambiguous_or_unknown_categories_remain_unassigned():
    assert match_existing_category("FOOD_AND_DRINK", [(uuid4(), "Dining"), (uuid4(), "Restaurants")]) is None
    assert match_existing_category("UNKNOWN", [(uuid4(), "Other")]) is None


@pytest.mark.parametrize(("provider_category", "expected_name"), [
    ("FOOD_AND_DRINK_RESTAURANT", "Drinks & Dining"),
    ("FOOD_AND_DRINK_RESTAURANTS", "Drinks & Dining"),
    ("FOOD_AND_DRINK_BAR", "Drinks & Dining"),
    ("FOOD_AND_DRINK_COFFEE", "Drinks & Dining"),
    ("FOOD_AND_DRINK_GROCERIES", "Groceries"),
    ("GENERAL_MERCHANDISE_SUPERSTORES", "Shopping"),
    ("GENERAL_MERCHANDISE_ONLINE_MARKETPLACES", "Shopping"),
    ("TRANSPORTATION_PUBLIC_TRANSIT", "Transportation"),
    ("TRAVEL_LODGING", "Travel"),
])
def test_detailed_provider_labels_map_to_actual_default_categories(provider_category, expected_name):
    categories = [(uuid4(), name) for name, _ in DEFAULT_BUDGET_CATEGORIES]
    expected = next(category_id for category_id, name in categories if name == expected_name)
    assert match_existing_category(provider_category, categories) == expected


def test_specific_category_beats_primary_fallback():
    coffee, dining = uuid4(), uuid4()
    assert match_existing_category(
        "FOOD_AND_DRINK_COFFEE", [(coffee, "Coffee"), (dining, "Drinks & Dining")]
    ) == coffee


def test_primary_fallback_does_not_resolve_ambiguity_or_partial_words():
    assert match_existing_category(
        "GENERAL_MERCHANDISE_SUPERSTORES", [(uuid4(), "Shopping"), (uuid4(), "General merchandise")]
    ) is None
    assert match_existing_category("TRAVELERS_INSURANCE", [(uuid4(), "Travel")]) is None
