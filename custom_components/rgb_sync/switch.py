"""Switches: whole-house link, audio reactive mode and audible feedback."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_AUDIO_REACTIVE,
    CONF_CUE,
    CONF_LINK,
    DOMAIN,
)
from .engine import SyncEngine


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    engine: SyncEngine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RgbSyncSwitch(engine, entry, CONF_LINK, "link"),
            RgbSyncSwitch(engine, entry, CONF_AUDIO_REACTIVE, "audio_reactive"),
            RgbSyncSwitch(engine, entry, CONF_CUE, "cue"),
        ]
    )


class RgbSyncSwitch(SwitchEntity, RestoreEntity):
    """Boolean hub option that survives restarts."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, engine: SyncEngine, entry: ConfigEntry, option: str, key: str) -> None:
        self.engine = engine
        self.option = option
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RGB Sync",
            model="Whole-house RGB controller",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            await self.engine.async_set_option(self.option, last.state == "on")
        self.async_on_remove(self.engine.async_add_listener(self.async_write_ha_state))

    @property
    def is_on(self) -> bool:
        if self.option == CONF_LINK:
            return self.engine.link
        if self.option == CONF_AUDIO_REACTIVE:
            return self.engine.audio_reactive
        return self.engine.cue_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.option == CONF_AUDIO_REACTIVE:
            return {
                "audio_entity": self.engine.audio_entity,
                "level": round(self.engine.audio_level, 3),
            }
        if self.option == CONF_CUE:
            return {"player": self.engine.cue_player}
        return {"devices": len(self.engine.enabled_devices())}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.engine.async_set_option(self.option, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.engine.async_set_option(self.option, False)
