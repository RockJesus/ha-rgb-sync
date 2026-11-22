"""Diagnostic sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .engine import SyncEngine
from .models import device_name


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    engine: SyncEngine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RgbSyncSensor(engine, entry, "online", "online_devices"),
            RgbSyncSensor(engine, entry, "audio", "audio_level"),
            RgbSyncSensor(engine, entry, "fps", "frame_rate"),
        ]
    )


class RgbSyncSensor(SensorEntity):
    """Live diagnostics for the sync engine."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, engine: SyncEngine, entry: ConfigEntry, kind: str, key: str) -> None:
        self.engine = engine
        self.kind = kind
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        if kind == "online":
            self._attr_native_unit_of_measurement = "台"
        elif kind == "audio":
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_native_unit_of_measurement = "fps"
            self._attr_state_class = SensorStateClass.MEASUREMENT
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
        if self.kind == "online":
            return float(self.engine.online_count)
        if self.kind == "audio":
            return round(self.engine.audio_level * 100, 1)
        return self.engine.fps

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.kind == "online":
            return {
                "total": len(self.engine.devices),
                "devices": {
                    device_name(device): bool(
                        self.engine.transports.get(str(device.get("id")))
                        and self.engine.transports[str(device.get("id"))].online
                    )
                    for device in self.engine.devices
                },
            }
        if self.kind == "audio":
            return {
                "reactive": self.engine.audio_reactive,
                "sensitivity": self.engine.sensitivity,
                "bands": self.engine.audio_bands[:16],
            }
        return {"fps": self.engine.fps, "devices": len(self.engine.devices)}
