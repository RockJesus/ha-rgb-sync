"""Numeric controls: effect speed, audio sensitivity, smoothing."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SENSITIVITY, CONF_SMOOTHING, CONF_SPEED, DOMAIN
from .engine import SyncEngine


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    engine: SyncEngine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RgbSyncNumber(engine, entry, CONF_SPEED, "speed", 1, 100, 1),
            RgbSyncNumber(engine, entry, CONF_SENSITIVITY, "sensitivity", 0, 100, 1),
            RgbSyncNumber(engine, entry, CONF_SMOOTHING, "smoothing", 0, 95, 5),
        ]
    )


class RgbSyncNumber(NumberEntity):
    """Hub-level numeric option."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(
        self,
        engine: SyncEngine,
        entry: ConfigEntry,
        option: str,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        self.engine = engine
        self.option = option
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RGB Sync",
            model="Whole-house RGB controller",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.engine.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> float:
        if self.option == CONF_SPEED:
            return float(self.engine.speed)
        if self.option == CONF_SENSITIVITY:
            return float(self.engine.sensitivity)
        return float(self.engine.smoothing)

    async def async_set_native_value(self, value: float) -> None:
        await self.engine.async_set_option(self.option, int(value))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.option == CONF_SENSITIVITY:
            return {"audio_level": round(self.engine.audio_level, 3)}
        return {}
