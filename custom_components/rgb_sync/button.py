"""Action buttons: identify, ping and cue test."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .engine import SyncEngine


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    engine: SyncEngine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RgbSyncButton(engine, entry, "identify", "identify"),
            RgbSyncButton(engine, entry, "ping", "ping"),
            RgbSyncButton(engine, entry, "test_cue", "test_cue"),
        ]
    )


class RgbSyncButton(ButtonEntity):
    """Hub action button."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = True

    def __init__(self, engine: SyncEngine, entry: ConfigEntry, key: str, action: str) -> None:
        self.engine = engine
        self.action = action
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RGB Sync",
            model="Whole-house RGB controller",
        )

    async def async_press(self) -> None:
        if self.action == "identify":
            await self.engine.async_identify()
        elif self.action == "ping":
            await self.engine.async_ping()
        else:
            await self.engine.async_cue(force=True)
