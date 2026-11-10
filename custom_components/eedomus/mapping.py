"""Helpers to map eedomus peripherals to Home Assistant platforms."""

from __future__ import annotations

from typing import Any

from .const import NAME_HINTS, USAGE_MAPPING

PLATFORM_LABELS = {
    "sensor": "Capteur",
    "binary_sensor": "Binaire",
    "switch": "Interrupteur",
    "light": "Lumière",
    "cover": "Volet",
}


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


def _clean_text(value: Any) -> str:
    """Normalize API text (strip + collapse spaces)."""
    return " ".join(str(value or "").replace("\ufffd", "").split()).strip()


def peripheral_label(periph: dict[str, Any], *, sort_by: str = "room") -> str:
    """Human-readable label for config-flow multi-select.

    sort_by:
      - room: "Pièce  ·  Nom  ·  Type"
      - type: "Type  ·  Pièce  ·  Nom"
    """
    periph_id = str(periph.get("periph_id", "?"))
    name = _clean_text(periph.get("name")) or f"Périphérique {periph_id}"
    room = _clean_text(periph.get("room_name")) or "Sans pièce"
    mapping = resolve_mapping(periph)
    platform = mapping.get("platform", "sensor")
    kind = PLATFORM_LABELS.get(platform, platform)

    if sort_by == "type":
        return f"{kind}  ·  {room}  ·  {name}  #{periph_id}"
    return f"{room}  ·  {name}  ·  {kind}  #{periph_id}"


def sort_peripherals(
    peripherals: list[dict[str, Any]], *, sort_by: str = "room"
) -> list[dict[str, Any]]:
    """Sort peripherals for a readable picker list."""

    def _key(item: dict[str, Any]) -> tuple:
        room = _clean_text(item.get("room_name")).casefold() or "zzz"
        name = _clean_text(item.get("name")).casefold()
        platform = resolve_mapping(item).get("platform", "sensor")
        kind = PLATFORM_LABELS.get(platform, platform).casefold()
        if sort_by == "type":
            return (kind, room, name)
        return (room, name, kind)

    return sorted(peripherals, key=_key)


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
