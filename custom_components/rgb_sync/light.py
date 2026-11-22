"""Light platform: one entity per device plus a whole-house group light."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EFFECTS, EFFECT_SOLID
from .engine import SyncEngine
from .models import device_name, device_pixels

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    engine: SyncEngine = hass.data[DOMAIN][entry.entry_id]
    entities: list[LightEntity] = [RgbSyncGroupLight(engine, entry)]
    for device in engine.devices:
        entities.append(RgbSyncDeviceLight(engine, entry, device))
    async_add_entities(entities)


class RgbSyncBaseLight(LightEntity):
    """Shared behaviour for the group and per-device lights."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
    _attr_effect_list = EFFECTS

    def __init__(self, engine: SyncEngine, entry: ConfigEntry) -> None:
        self.engine = engine
        self.entry = entry

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.engine.async_add_listener(self.async_write_ha_state))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"sync_link": self.engine.link}


class RgbSyncGroupLight(RgbSyncBaseLight):
    """Whole-house light: every enabled device follows this entity."""

    _attr_translation_key = "all_lights"

    def __init__(self, engine: SyncEngine, entry: ConfigEntry) -> None:
        super().__init__(engine, entry)
        self._attr_unique_id = f"{entry.entry_id}_all_lights"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RGB Sync",
            model="Whole-house RGB controller",
        )

    @property
    def is_on(self) -> bool:
        return self.engine.any_on

    @property
    def brightness(self) -> int | None:
        state = self.engine.representative()
        return state.brightness if state else 255

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        state = self.engine.representative()
        return state.rgb if state else None

    @property
    def effect(self) -> str | None:
        return self.engine.common_effect()

    async def async_turn_on(self, **kwargs: Any) -> None:
        data: dict[str, Any] = {"on": True, "source": "group"}
        if ATTR_BRIGHTNESS in kwargs:
            data["brightness"] = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGB_COLOR in kwargs:
            data["rgb"] = kwargs[ATTR_RGB_COLOR]
        if ATTR_EFFECT in kwargs:
            data["effect"] = kwargs[ATTR_EFFECT]
        await self.engine.async_set_all(**data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.engine.async_set_all(on=False, source="group")


class RgbSyncDeviceLight(RgbSyncBaseLight):
    """Single lamp / strip."""

    _attr_name = None

    def __init__(self, engine: SyncEngine, entry: ConfigEntry, device: dict[str, Any]) -> None:
        super().__init__(engine, entry)
        self.device = device
        self.device_id = str(device.get("id"))
        self._attr_unique_id = f"{entry.entry_id}_{self.device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self.device_id}")},
            name=device_name(device),
            manufacturer="RGB Sync",
            model=str(device.get("protocol", "")).upper() or "RGB device",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        transport = self.engine.transports.get(self.device_id)
        return bool(transport and transport.online)

    @property
    def is_on(self) -> bool:
        return self.engine.state(self.device_id).on

    @property
    def brightness(self) -> int | None:
        return self.engine.state(self.device_id).brightness

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self.engine.state(self.device_id).rgb

    @property
    def effect(self) -> str | None:
        return self.engine.state(self.device_id).effect

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        transport = self.engine.transports.get(self.device_id)
        return {
            "protocol": self.device.get("protocol"),
            "pixels": device_pixels(self.device),
            "speed": self.engine.state(self.device_id).speed,
            "online": bool(transport and transport.online),
            "last_error": transport.last_error if transport else "not configured",
            "sync_link": self.engine.link,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        data: dict[str, Any] = {"on": True, "source": "user"}
        if ATTR_BRIGHTNESS in kwargs:
            data["brightness"] = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGB_COLOR in kwargs:
            data["rgb"] = kwargs[ATTR_RGB_COLOR]
            data["palette"] = ["#{:02x}{:02x}{:02x}".format(*kwargs[ATTR_RGB_COLOR])]
        if ATTR_EFFECT in kwargs:
            data["effect"] = kwargs[ATTR_EFFECT]
            if kwargs[ATTR_EFFECT] == EFFECT_SOLID and "rgb" not in data:
                data["palette"] = [self.engine._rgb_hex(self.engine.state(self.device_id).rgb)]
        await self.engine.async_set(self.device_id, **data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.engine.async_set(self.device_id, on=False, source="user")
