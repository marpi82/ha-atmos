"""Entity-registry helpers for Info part slots (Home Assistant imports OK)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .info_map import info_part_uid_bare


def registered_info_part_indices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    skupina: int,
    caption_id: int,
    *,
    domain: str | None = None,
) -> set[int]:
    """Return part indices already registered for one Info row.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        skupina: Info group id.
        caption_id: Caption text id.
        domain: Limit to ``sensor`` / ``binary_sensor``, or both when omitted.
    """
    registry = er.async_get(hass)
    bare = f"{entry.entry_id}_{info_part_uid_bare(skupina, caption_id)}"
    prefix = f"{entry.entry_id}_g{skupina}_c{caption_id}_p"
    domains = {domain} if domain is not None else {"sensor", "binary_sensor"}
    found: set[int] = set()
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        if ent.domain not in domains or ent.platform != DOMAIN:
            continue
        uid = ent.unique_id
        if uid == bare:
            found.add(0)
            continue
        if uid.startswith(prefix):
            tail = uid[len(prefix) :]
            if tail.isdigit():
                found.add(int(tail))
    return found


def remove_legacy_info_uid(
    hass: HomeAssistant,
    entry: ConfigEntry,
    skupina: int,
    caption_id: int,
    *,
    domain: str,
) -> None:
    """Drop the pre-a6 unique_id without ``_p`` when present."""
    registry = er.async_get(hass)
    bare = f"{entry.entry_id}_{info_part_uid_bare(skupina, caption_id)}"
    entity_id = registry.async_get_entity_id(domain, DOMAIN, bare)
    if entity_id is not None:
        registry.async_remove(entity_id)


__all__ = ["registered_info_part_indices", "remove_legacy_info_uid"]
