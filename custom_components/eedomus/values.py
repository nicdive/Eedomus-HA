"""Helpers to extract current values from eedomus payloads."""

from __future__ import annotations

from typing import Any


VALUE_KEYS = (
    "last_value",
    "value",
    "current_value",
    "val",
)


def extract_last_value(data: dict[str, Any]) -> Any:
    """Return the best current value field from a peripheral/caract payload."""
    for key in VALUE_KEYS:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def has_usable_value(data: dict[str, Any]) -> bool:
    """True when the payload already carries a readable current value."""
    return extract_last_value(data) is not None


def merge_value_fields(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Merge source into target and normalize last_value when aliases are used."""
    merged = {**target, **source}
    value = extract_last_value(merged)
    if value is not None:
        merged["last_value"] = value
    return merged
