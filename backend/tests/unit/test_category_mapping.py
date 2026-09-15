from uuid import uuid4
from app.domain.category_mapping import match_existing_category


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
