"""Conservative defaults that only select an existing, unambiguous category."""
import re
from uuid import UUID


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower().replace("&", " and ")))


ALIASES = (
    {"groceries", "grocery", "supermarkets"},
    {"dining", "dining out", "restaurant", "restaurants", "food and drink", "food and dining", "drinks and dining"},
    {"coffee", "coffee shops"},
    {"transportation", "transport", "travel transportation"},
    {"gas", "gas stations", "fuel"},
    {"housing", "rent", "rent and utilities"},
    {"utilities", "utilities bills"},
    {"entertainment", "recreation"},
    {"shopping", "general merchandise"},
    {"health", "healthcare", "medical"},
    {"personal care"},
    {"travel"},
    {"insurance"},
)


def match_existing_category(provider_category: str, categories: list[tuple[UUID, str]]) -> UUID | None:
    source = normalized(provider_category)
    names = [(category_id, normalized(name)) for category_id, name in categories]
    exact = [category_id for category_id, name in names if name == source]
    if exact:
        return exact[0] if len(exact) == 1 else None
    # Prefer detailed provider labels (e.g. FOOD_AND_DRINK_GROCERIES)
    # over their broad primary category. Fall back to the primary prefix for
    # labels such as GENERAL_MERCHANDISE_SUPERSTORES. Match whole words so
    # unrelated labels cannot accidentally pick up a partial category name.
    # Equal-strength matches stay unassigned.
    candidates: dict[UUID, tuple[int, int]] = {}
    for aliases in ALIASES:
        matches = [
            (1, len(alias)) if source.endswith(" " + alias) else
            (0, len(alias)) if source == alias else
            (-1, len(alias))
            for alias in aliases
            if source == alias or source.endswith(" " + alias) or source.startswith(alias + " ")
        ]
        if not matches:
            continue
        score = max(matches)
        for category_id, name in names:
            if name in aliases:
                candidates[category_id] = max(candidates.get(category_id, (-1, -1)), score)
    if not candidates:
        return None
    best = max(candidates.values())
    winners = [category_id for category_id, score in candidates.items() if score == best]
    return winners[0] if len(winners) == 1 else None
