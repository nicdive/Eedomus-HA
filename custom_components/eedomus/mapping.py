"""Helpers to map eedomus peripherals to Home Assistant platforms."""

from __future__ import annotations

from typing import Any

from .const import NAME_HINTS, USAGE_MAPPING


def resolve_mapping(periph: dict[str, Any]) -> dict[str, Any]:
    """Resolve HA platform metadata for a peripheral."""
    usage_id = str(periph.get("usage_id") or "").strip()
    if usage_id in USAGE_MAPPING:
        return dict(USAGE_MAPPING[usage_id])

    haystack = " ".join(
        str(periph.get(key) or "").lower()
        for key in ("usage_name", "name")
    )
    for keywords, mapping in NAME_HINTS:
        if any(keyword in haystack for keyword in keywords):
            return dict(mapping)

    # Default: read-only sensor so the user still sees the value.
    return {"platform": "sensor"}


def peripheral_label(periph: dict[str, Any]) -> str:
    """Human-readable label for config-flow multi-select."""
    periph_id = str(periph.get("periph_id", "?"))
    name = str(periph.get("name") or f"Périphérique {periph_id}")
    room = str(periph.get("room_name") or "").strip()
    usage = str(periph.get("usage_name") or "").strip()
    mapping = resolve_mapping(periph)
    platform = mapping.get("platform", "sensor")

    parts = [f"[{platform}] {name}"]
    if room:
        parts.append(f"({room})")
    if usage:
        parts.append(f"— {usage}")
    parts.append(f"#{periph_id}")
    return " ".join(parts)


def coerce_number(value: Any) -> float | int | str | None:
    """Best-effort numeric coercion for sensor states."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return str(value)
    if number.is_integer():
        return int(number)
    return number


def is_on_value(value: Any) -> bool:
    """Interpret eedomus on/off style values."""
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in {"1", "100", "on", "true", "yes", "ouvert", "open"}:
        return True
    if text in {"0", "off", "false", "no", "fermé", "ferme", "closed"}:
        return False
    try:
        return float(text.replace(",", ".")) > 0
    except ValueError:
        return bool(text)
