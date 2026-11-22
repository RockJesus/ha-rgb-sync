"""RGB Sync: whole-house RGB synchronisation for Home Assistant."""

from __future__ import annotations

import inspect
import logging
import os

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import BEEP_PATH, CONF_DEVICE_ID, CONF_DEVICES, DOMAIN, PLATFORMS
from .engine import SyncEngine
from .services import async_register_services
from .websocket_api import async_register_websocket

_LOGGER = logging.getLogger(__name__)

_HEX = set("0123456789abcdef")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one RGB Sync hub entry."""
    await _async_prune_device_entities(hass, entry)

    engine = SyncEngine(hass, entry)
    await engine.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = engine

    await _async_register_static(hass)
    await async_register_services(hass)
    async_register_websocket(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a hub entry and release every transport."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    engine: SyncEngine | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if engine is not None:
        await engine.async_stop()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_prune_device_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop per-device entities whose device has been removed from options."""
    devices = entry.options.get(CONF_DEVICES, entry.data.get(CONF_DEVICES, []))
    valid = {str(device.get(CONF_DEVICE_ID)) for device in devices}
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform != DOMAIN:
            continue
        unique_id = entity.unique_id
        if not unique_id.startswith(prefix):
            continue
        suffix = unique_id[len(prefix) :]
        if len(suffix) == 10 and set(suffix) <= _HEX and suffix not in valid:
            _LOGGER.info("Removing stale entity %s (device %s)", entity.entity_id, suffix)
            removed = registry.async_remove(entity.entity_id)
            if inspect.isawaitable(removed):
                await removed


async def _async_register_static(hass: HomeAssistant) -> None:
    """Serve the short confirmation beep used by audible feedback."""
    store = hass.data.setdefault(DOMAIN, {})
    if store.get("static_registered"):
        return
    if getattr(hass, "http", None) is None:  # pragma: no cover - http not loaded
        return
    beep = os.path.join(os.path.dirname(__file__), "beep.wav")
    if not os.path.isfile(beep):
        _LOGGER.warning("Beep asset missing, audible feedback disabled")
        return
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(BEEP_PATH, beep, cache_headers=False)]
        )
    except (AttributeError, RuntimeError, ValueError) as err:  # pragma: no cover
        _LOGGER.debug("Static path registration skipped: %s", err)
    store["static_registered"] = True
