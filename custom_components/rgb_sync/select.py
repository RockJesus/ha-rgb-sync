"""Scene preset selector."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCENES
from .engine import SyncEngine

CUSTOM = "自定义"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    engine: SyncEngine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RgbSyncScene(engine, entry)])


class RgbSyncScene(SelectEntity):
    """Applies a palette + effect preset to every device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "scene"
    _attr_options = [CUSTOM, *SCENES.keys()]

    def __init__(self, engine: SyncEngine, entry: ConfigEntry) -> None:
        self.engine = engine
        self._attr_unique_id = f"{entry.entry_id}_scene"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RGB Sync",
            model="Whole-house RGB controller",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.engine.async_add_listener(self.async_write_ha_state))

    @property
    def current_option(self) -> str:
        return self.engine.scene

    async def async_select_option(self, option: str) -> None:
        await self.engine.async_apply_scene(option)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"presets": sorted(SCENES.keys())}
