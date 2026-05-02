import re
from functools import lru_cache
from typing import Final


# Ordered by specificity. Longer multi-word rules should remain ahead of broad terms.
_CATEGORY_RULES: list[tuple[str, str]] = [
    ("conference table", "conference_table"),
    ("chest of drawers", "chest_of_drawers"),
    ("chest of drawer", "chest_of_drawers"),
    ("serving trolley", "serving_trolley"),
    ("corner cabinet", "corner_cabinet"),
    ("nest of tables", "nest_of_tables"),
    ("bedside table", "bedside_table"),
    ("writing desk", "writing_desk"),
    ("sewing table", "sewing_table"),
    ("dining chair", "dining_chair"),
    ("dining table", "dining_table"),
    ("coffee table", "coffee_table"),
    ("plant stand", "plant_stand"),
    ("round table", "dining_table"),
    ("bar cabinet", "bar_cabinet"),
    ("small table", "small_side_table"),
    ("hall table", "hall_table"),
    ("of drawers", "chest_of_drawers"),
    ("side table", "side_table"),
    ("secretary", "secretary_cabinet"),
    ("armchairs", "armchair"),
    ("armchair", "armchair"),
    ("highboard", "highboard"),
    ("sideboard", "sideboard"),
    ("bookshelf", "bookshelf"),
    ("shelving", "shelving"),
    ("trolley", "serving_trolley"),
    ("cabinet", "cabinet"),
    ("chairs", "dining_chair"),
    ("chair", "dining_chair"),
    ("mirror", "mirror"),
    ("poster", "poster"),
    ("bench", "bench"),
    ("stool", "stool"),
    ("sofa", "sofa"),
    ("lamp", "lamp"),
]


def _normalize_text(value: str) -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


_COMPILED_CATEGORY_RULES: Final[tuple[tuple[str, str], ...]] = tuple(
    sorted(
        (
            (_normalize_text(match_key), category)
            for match_key, category in _CATEGORY_RULES
            if _normalize_text(match_key)
        ),
        key=lambda rule: len(rule[0]),
        reverse=True,
    )
)

def _to_display_item_type(category: str) -> str:
    return category.replace("_", " ").strip().title()


_SUPPORTED_ITEM_TYPES: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(_to_display_item_type(category) for _match_key, category in _COMPILED_CATEGORY_RULES)
)


@lru_cache(maxsize=4096)
def _resolve_category_from_normalized_title(normalized_title: str) -> str | None:
    for match_key, category in _COMPILED_CATEGORY_RULES:
        if match_key in normalized_title:
            return category
    return None


def map_shopify_title_to_item_type(title: str | None) -> str | None:
    """Resolve a Shopify item title into a canonical item_type.

    If no category rule matches, the original title is returned unchanged.
    """
    if title is None:
        return None

    raw_title = str(title).strip()
    if not raw_title:
        return raw_title

    normalized_title = _normalize_text(raw_title)
    resolved_category = _resolve_category_from_normalized_title(normalized_title)
    return _to_display_item_type(resolved_category) if resolved_category else raw_title


def get_supported_shopify_item_types() -> tuple[str, ...]:
    return _SUPPORTED_ITEM_TYPES
