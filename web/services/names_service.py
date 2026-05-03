"""Display-name lookup for stackable item categories.

Reads the per-category JSON files produced by tools/extract_names.py and
exposes id->name maps. Files are cached after first load.
"""

from __future__ import annotations

import json
from typing import Final

from web import config


SUPPORTED_CATEGORIES: Final[tuple[str, ...]] = (
    "consumables",
    "materials",
    "important_items",
)

_cache: dict[str, dict[int, str]] = {}


def get_names(category: str) -> dict[int, str]:
    """Return the id->name map for a category. Empty dict if the file is missing."""
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"unknown category {category!r}")
    if category in _cache:
        return _cache[category]

    path = config.NAMES_DIR / f"{category}.json"
    if not path.exists():
        _cache[category] = {}
        return _cache[category]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _cache[category] = {}
        return _cache[category]

    out: dict[int, str] = {}
    for record in data.get("records", []):
        item_id = record.get("id")
        name = record.get("name")
        if isinstance(item_id, int) and isinstance(name, str):
            out[item_id] = name
    _cache[category] = out
    return out


def display_name(category: str, item_id: int) -> str:
    """Return the resolved name or a synthetic fallback like 'Material 12345'."""
    names = get_names(category)
    if item_id in names:
        return names[item_id]
    label = category.replace("_", " ").title().rstrip("s")
    return f"{label} {item_id}"
